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
        [chunk_id={chunk.id}] (section={chunk.section})
        {chunk.text}
        
    Args:
        chunks: List of TranscriptChunk instances
        
    Returns:
        Formatted string with all chunks
    """
    formatted_parts = []
    for chunk in chunks:
        chunk_header = f"[chunk_id={chunk.id}] (section={chunk.section})"
        formatted_parts.append(f"{chunk_header}\n{chunk.text}")
    
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


def answer_question(transcript: Transcript, question: str) -> dict:
    """
    Answer a question about the transcript using grounded Q&A.
    
    Process:
    1. Retrieve top-K chunks using retrieve_top_k
    2. Check token budget (sum of chunk.token_count <= MAX_TOKENS_PER_CALL)
    3. Trim chunks from bottom if needed
    4. Format chunks as context
    5. Call OpenAI with QA prompts
    6. Parse JSON response
    7. Validate citations
    8. Return answer with citations and confidence
    
    Args:
        transcript: Transcript instance to search
        question: Question string from user
        
    Returns:
        Dict with:
            - answer (str): The answer text
            - citations (list): List of {chunk_id, short_quote}
            - confidence (str): high|medium|low
            - chunks_used (int): Number of chunks used
            
    Raises:
        ValueError: If response JSON is invalid
        Exception: For OpenAI API errors
    """
    # Step 1: Retrieve top-K chunks
    chunks = retrieve_top_k(transcript, question, k=DEFAULT_K)
    
    if not chunks:
        # No chunks available - transcript may not be chunked yet
        return {
            "answer": "No transcript content available to answer this question.",
            "citations": [],
            "confidence": "low",
            "chunks_used": 0
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
    client = OpenAI()
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
        max_tokens=1000
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
    
    # Step 9: Return final result
    return {
        "answer": result.get("answer", ""),
        "citations": validated_citations,
        "confidence": validated_confidence,
        "chunks_used": len(chunks)
    }
