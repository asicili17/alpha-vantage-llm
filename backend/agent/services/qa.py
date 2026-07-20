"""
Q&A pipeline using OpenAI GPT-4o-mini with grounded retrieval.

Implements:
1. Retrieve top-K chunks using semantic/keyword search
2. Format chunks as context with citation markers
3. Call LLM with grounding instructions
4. Parse and validate citations

Results are NOT cached (each question is unique).
"""

import json
import logging
from typing import Dict, List

from django.conf import settings
from openai import OpenAI

from agent.services.prompts import QA_SYSTEM_PROMPT, QA_USER_PROMPT
from transcripts.models import Transcript
from transcripts.services.chunking import retrieve_top_k


logger = logging.getLogger(__name__)

# Constants
MODEL = getattr(settings, 'QA_MODEL', 'gpt-4o-mini')
MAX_TOKENS_PER_CALL = 20000  # Conservative limit for total chunk tokens
DEFAULT_K = 8  # Number of chunks to retrieve
VALID_CONFIDENCE = {"high", "medium", "low"}  # Allowed confidence values


def _format_chunks(chunks) -> str:
    """
    Format chunks for LLM context with citation markers.
    
    Format:
        === CHUNK ID: {chunk.id} ===
        Section: {chunk.section}
        {chunk.text}
        
    Args:
        chunks: List of TranscriptChunk instances
        
    Returns:
        Formatted string with all chunks
    """
    formatted_parts = []
    for chunk in chunks:
        chunk_header = f"=== CHUNK ID: {chunk.id} ==="
        section_line = f"Section: {chunk.section}"
        formatted_parts.append(f"{chunk_header}\n{section_line}\n{chunk.text}")
    
    return "\n\n---\n\n".join(formatted_parts)


def _strip_markdown_json(text: str) -> str:
    """
    Strip markdown code fences from JSON response if present.
    
    OpenAI sometimes wraps JSON in ```json ... ```
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]  # Remove ```json
    elif text.startswith("```"):
        text = text[3:]  # Remove ```
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _parse_json_response(response_text: str) -> dict:
    """
    Parse JSON from OpenAI response.
    
    Args:
        response_text: Raw response from OpenAI
        
    Returns:
        Parsed JSON dict
        
    Raises:
        ValueError: If JSON is invalid
    """
    cleaned = _strip_markdown_json(response_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON response from Q&A: {str(e)}\nResponse: {response_text[:200]}"
        raise ValueError(error_msg)


def _validate_citations(citations: List[Dict], valid_chunk_ids: set) -> List[Dict]:
    """
    Filter citations to only include those with valid chunk IDs.
    
    Args:
        citations: List of citation dicts with chunk_id field
        valid_chunk_ids: Set of valid chunk ID strings
        
    Returns:
        Filtered list of citations
    """
    original_count = len(citations)
    filtered = [cite for cite in citations if cite.get("chunk_id") in valid_chunk_ids]
    
    dropped = original_count - len(filtered)
    if dropped > 0:
        logger.warning(f"Dropped {dropped} citations with invalid chunk_id references")
    
    return filtered


def _validate_confidence(confidence: str) -> str:
    """
    Validate and normalize confidence value.
    
    Args:
        confidence: Confidence string from LLM response
        
    Returns:
        Normalized confidence ("high", "medium", or "low")
    """
    # Normalize to lowercase for comparison
    normalized = confidence.lower().strip()
    
    if normalized in VALID_CONFIDENCE:
        return normalized
    
    # Default invalid values to "low"
    logger.warning(f"Invalid confidence value '{confidence}', defaulting to 'low'")
    return "low"


def answer_question(
    transcript: Transcript, 
    question: str,
    section_filter: str = None,
    speaker_filter: str = None,
    min_chunks_threshold: int = 2
) -> dict:
    """
    Answer a question about the transcript using grounded Q&A.
    
    Process:
    1. Retrieve top-K chunks using retrieve_top_k with optional filters
    2. Check token budget (sum of chunk.token_count <= MAX_TOKENS_PER_CALL)
    3. Trim chunks from bottom if needed
    4. Apply retrieval quality gate (Phase 5)
    5. Format chunks as context
    6. Call OpenAI with QA prompts
    7. Parse JSON response
    8. Validate citations
    9. Return answer with citations and confidence
    
    Args:
        transcript: Transcript instance to search
        question: Question string from user
        section_filter: Optional filter for 'prepared' or 'qa' sections (Phase 4)
        speaker_filter: Optional speaker name/role filter (Phase 4)
        min_chunks_threshold: Minimum chunks required for confident answer (Phase 5)
        
    Returns:
        Dict with:
            - answer (str): The answer text
            - citations (list): List of {chunk_id, short_quote}
            - confidence (str): high|medium|low
            - chunks_used (int): Number of chunks used
            - retrieval_quality (str): 'sufficient' or 'insufficient'
            
    Raises:
        ValueError: If response JSON is invalid
        Exception: For OpenAI API errors
    """
    # Step 1: Retrieve top-K chunks with filters (Phase 4)
    # TODO: Get chunks_before count for logging
    chunks_before_filter = None  # Would need to query without filters to get this
    
    chunks = retrieve_top_k(
        transcript, 
        question, 
        k=DEFAULT_K,
        section_filter=section_filter,
        speaker_filter=speaker_filter
    )
    
    # Log filter application if filters were used
    if section_filter or speaker_filter:
        from chat.services.query_logging import log_filter_application
        log_filter_application(
            section_filter=section_filter,
            speaker_filter=speaker_filter,
            chunks_before=chunks_before_filter or 0,  # Would need actual count
            chunks_after=len(chunks)
        )
    
    # Phase 5: Retrieval quality gate
    quality_assessment = 'sufficient' if (chunks and len(chunks) >= min_chunks_threshold) else 'insufficient'
    
    # Log retrieval quality gate evaluation
    from chat.services.query_logging import log_retrieval_quality_gate
    log_retrieval_quality_gate(
        chunks_retrieved=len(chunks) if chunks else 0,
        threshold=min_chunks_threshold,
        quality=quality_assessment,
        query=question
    )
    
    if not chunks or len(chunks) < min_chunks_threshold:
        return {
            "answer": "I don't have enough relevant information to answer this question confidently. Could you rephrase or provide more context?",
            "citations": [],
            "confidence": "low",
            "chunks_used": len(chunks) if chunks else 0,
            "retrieval_quality": "insufficient"
        }
    
    # Step 2: Check token budget
    total_tokens = sum(chunk.token_count for chunk in chunks)
    
    # Step 3: Trim chunks if exceeding budget
    if total_tokens > MAX_TOKENS_PER_CALL:
        logger.info(f"Token budget exceeded ({total_tokens} > {MAX_TOKENS_PER_CALL}), trimming chunks")
        trimmed_chunks = []
        current_tokens = 0
        
        for chunk in chunks:
            if current_tokens + chunk.token_count <= MAX_TOKENS_PER_CALL:
                trimmed_chunks.append(chunk)
                current_tokens += chunk.token_count
            else:
                break
        
        chunks = trimmed_chunks
        logger.info(f"Trimmed to {len(chunks)} chunks with {current_tokens} tokens")
    
    # Step 4: Format chunks
    formatted_chunks = _format_chunks(chunks)
    valid_chunk_ids = {str(chunk.id) for chunk in chunks}
    
    # Step 5: Call OpenAI
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    user_prompt = QA_USER_PROMPT.format(
        question=question,
        formatted_chunks=formatted_chunks
    )
    
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": QA_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        temperature=0.3,
        max_tokens=2000
    )
    
    # Step 6: Parse response
    result_text = response.choices[0].message.content
    result = _parse_json_response(result_text)
    
    # Step 7: Validate citations
    citations = result.get("citations", [])
    validated_citations = _validate_citations(citations, valid_chunk_ids)
    
    # Step 8: Validate confidence
    raw_confidence = result.get("confidence", "low")
    validated_confidence = _validate_confidence(raw_confidence)
    
    # Step 9: Return final result with retrieval quality
    return {
        "answer": result.get("answer", ""),
        "citations": validated_citations,
        "confidence": validated_confidence,
        "chunks_used": len(chunks),
        "retrieval_quality": "sufficient"
    }
