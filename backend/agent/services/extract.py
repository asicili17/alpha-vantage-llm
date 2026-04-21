"""
Extraction pipeline using OpenAI GPT-4o-mini with structured JSON schema output.

Implements a map/reduce approach:
1. Map: Extract from each chunk independently
2. Reduce: Merge and deduplicate extractions into final output

Results are cached in the Artifact model.
"""

import json
import logging
from typing import Dict, List

from django.conf import settings
from openai import OpenAI

from agent.models import Artifact
from agent.schemas import EXTRACTION_SCHEMA
from agent.services.prompts import (
    EXTRACT_MAP_SYSTEM_PROMPT,
    EXTRACT_MAP_USER_PROMPT,
    EXTRACT_REDUCE_SYSTEM_PROMPT,
    EXTRACT_REDUCE_USER_PROMPT
)
from transcripts.models import Transcript
from transcripts.services.chunking import get_or_create_chunks, estimate_tokens


logger = logging.getLogger(__name__)

# Constants
MODEL = getattr(settings, 'EXTRACT_MODEL', 'gpt-4o-mini')
PROMPT_VERSION = "v1"
MAX_TOKENS_PER_CALL = 20000  # Conservative limit for token count
MAX_REDUCE_TOKENS = 15000  # Safe limit for reduce input to avoid token overflow


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


def _parse_json_response(response_text: str, retry_context: str = None) -> dict:
    """
    Parse JSON from OpenAI response.
    
    Args:
        response_text: Raw response from OpenAI
        retry_context: Context string for error messages
        
    Returns:
        Parsed JSON dict
        
    Raises:
        ValueError: If JSON is invalid
    """
    cleaned = _strip_markdown_json(response_text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        error_msg = f"Invalid JSON response"
        if retry_context:
            error_msg += f" ({retry_context})"
        error_msg += f": {str(e)}\nResponse: {response_text[:200]}"
        raise ValueError(error_msg)


def _map_chunk(chunk, client: OpenAI) -> dict:
    """
    Extract structured information from a single chunk.
    
    Args:
        chunk: TranscriptChunk instance
        client: OpenAI client instance
        
    Returns:
        Dict with extraction matching EXTRACTION_SCHEMA
        
    Raises:
        ValueError: If response JSON is invalid after retry
        Exception: For OpenAI API errors
    """
    chunk_id = str(chunk.id)
    user_prompt = EXTRACT_MAP_USER_PROMPT.format(
        chunk_id=chunk_id,
        chunk_text=chunk.text
    )
    
    # First attempt
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_MAP_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=1500
        )
        
        result_text = response.choices[0].message.content
        return _parse_json_response(result_text, "extract map phase")
        
    except ValueError as e:
        # Retry once with stricter prompt
        retry_prompt = user_prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no explanations."
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_MAP_SYSTEM_PROMPT},
                {"role": "user", "content": retry_prompt}
            ],
            temperature=0.1,
            max_tokens=1500
        )
        
        result_text = response.choices[0].message.content
        return _parse_json_response(result_text, "extract map phase retry")


def _reduce(map_outputs: List[dict], symbol: str, quarter: str, client: OpenAI) -> dict:
    """
    Merge multiple chunk extractions into a final extraction.
    
    Args:
        map_outputs: List of dicts from _map_chunk
        symbol: Stock symbol (for fallback company name)
        quarter: Quarter string (for fallback period)
        client: OpenAI client instance
        
    Returns:
        Dict with merged extraction matching EXTRACTION_SCHEMA
        
    Raises:
        ValueError: If response JSON is invalid after retry
        Exception: For OpenAI API errors
    """
    # Format extractions for the reduce prompt
    extractions_text = json.dumps(map_outputs, indent=2)
    
    user_prompt = EXTRACT_REDUCE_USER_PROMPT.format(extractions=extractions_text)
    
    # First attempt
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_REDUCE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        result_text = response.choices[0].message.content
        result = _parse_json_response(result_text, "extract reduce phase")
        
        # Fallback for company and period if empty
        if not result.get("company"):
            result["company"] = symbol
        if not result.get("period"):
            result["period"] = quarter
            
        return result
        
    except ValueError as e:
        # Retry once with stricter prompt
        retry_prompt = user_prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no explanations."
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": EXTRACT_REDUCE_SYSTEM_PROMPT},
                {"role": "user", "content": retry_prompt}
            ],
            temperature=0.1,
            max_tokens=2000
        )
        
        result_text = response.choices[0].message.content
        result = _parse_json_response(result_text, "extract reduce phase retry")
        
        # Fallback for company and period if empty
        if not result.get("company"):
            result["company"] = symbol
        if not result.get("period"):
            result["period"] = quarter
            
        return result


def _validate_citations_in_list(items, field_name, valid_chunk_ids, citation_key='citation_chunk_id'):
    """
    Filter list items to only include those with valid citation chunk IDs.
    
    Args:
        items: List of dicts with citation_key field, or list of strings
        field_name: Name for logging
        valid_chunk_ids: Set of valid chunk ID strings
        citation_key: Key to check in dict items (ignored for string items)
        
    Returns:
        Filtered list
    """
    original_count = len(items)
    
    # Check if items are dicts or strings
    if items and isinstance(items[0], dict):
        filtered = [item for item in items if item.get(citation_key) in valid_chunk_ids]
    else:
        # List of strings
        filtered = [cid for cid in items if cid in valid_chunk_ids]
    
    dropped = original_count - len(filtered)
    if dropped > 0:
        logger.warning(f"Dropped {dropped} {field_name} with invalid citation references")
    
    return filtered


def get_or_create_extraction(transcript: Transcript) -> Artifact:
    """
    Get cached extraction or create a new one using map/reduce.
    
    Process:
    1. Check if artifact exists in cache
    2. If not, get chunks from transcript
    3. Validate chunk token counts (relies on Phase 3 chunking limits)
    4. Map: Extract from each chunk
    5. Reduce: Merge extractions with deduplication
    6. Persist artifact
    
    Args:
        transcript: Transcript instance to extract from
        
    Returns:
        Artifact instance with extraction in content field
        
    Raises:
        Exception: For OpenAI API errors or invalid responses
    """
    # Check cache
    try:
        artifact = Artifact.objects.get(
            transcript=transcript,
            artifact_type="extraction",
            model=MODEL,
            prompt_version=PROMPT_VERSION
        )
        return artifact
    except Artifact.DoesNotExist:
        pass
    
    # Initialize OpenAI client
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    # Get chunks
    chunks = get_or_create_chunks(transcript)
    
    if not chunks:
        raise ValueError(f"No chunks found for transcript {transcript.id}")
    
    # Validate chunk sizes (safety check - Phase 3 should enforce this)
    for chunk in chunks:
        chunk_tokens = estimate_tokens(chunk.text)
        if chunk_tokens > MAX_TOKENS_PER_CALL:
            raise ValueError(
                f"Chunk {chunk.chunk_index} exceeds token limit: "
                f"{chunk_tokens} > {MAX_TOKENS_PER_CALL}. "
            )
    
    # Map phase: Extract from each chunk
    map_outputs = []
    for chunk in chunks:
        chunk_extraction = _map_chunk(chunk, client)
        map_outputs.append(chunk_extraction)
    
    # Reduce phase: Merge extractions with hierarchical reduction if needed
    # Estimate tokens in reduce input
    reduce_input_text = json.dumps(map_outputs)
    reduce_tokens = len(reduce_input_text) // 4  # Simple token estimate
    
    if reduce_tokens > MAX_REDUCE_TOKENS:
        # Hierarchical reduce: batch reduce, then final reduce
        batch_size = 10  # Smaller batch for extractions (more complex than summaries)
        batch_extractions = []
        
        for i in range(0, len(map_outputs), batch_size):
            batch = map_outputs[i:i+batch_size]
            batch_extraction = _reduce(batch, transcript.symbol, transcript.quarter, client)
            batch_extractions.append(batch_extraction)
        
        # Final reduce of batch extractions
        final_extraction = _reduce(batch_extractions, transcript.symbol, transcript.quarter, client)
    else:
        # Direct reduce
        final_extraction = _reduce(map_outputs, transcript.symbol, transcript.quarter, client)
    
    # Validate citations: ensure all citation_chunk_ids reference valid chunks
    valid_chunk_ids = {str(chunk.id) for chunk in chunks}
    validated_extraction = final_extraction.copy()
    
    # Filter invalid citations from all fields
    validated_extraction['key_metrics'] = _validate_citations_in_list(
        validated_extraction.get('key_metrics', []),
        'key_metrics',
        valid_chunk_ids
    )
    
    validated_extraction['guidance'] = _validate_citations_in_list(
        validated_extraction.get('guidance', []),
        'guidance',
        valid_chunk_ids
    )
    
    validated_extraction['risks'] = _validate_citations_in_list(
        validated_extraction.get('risks', []),
        'risks',
        valid_chunk_ids
    )
    
    if 'tone' in validated_extraction and 'citation_chunk_ids' in validated_extraction['tone']:
        validated_extraction['tone']['citation_chunk_ids'] = _validate_citations_in_list(
            validated_extraction['tone']['citation_chunk_ids'],
            'tone.citation_chunk_ids',
            valid_chunk_ids
        )
    
    # Persist artifact
    artifact = Artifact.objects.create(
        transcript=transcript,
        artifact_type="extraction",
        model=MODEL,
        prompt_version=PROMPT_VERSION,
        content=validated_extraction
    )
    
    return artifact
