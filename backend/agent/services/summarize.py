"""
Map/Reduce summarization pipeline using OpenAI GPT-4o-mini.

Implements a two-pass approach:
1. Map: Summarize each chunk independently
2. Reduce: Merge all chunk summaries into a final summary

Results are cached in the Artifact model.
"""

import concurrent.futures
import json
import re
from typing import Dict, List, Tuple

from django.conf import settings
from openai import OpenAI

from agent.models import Artifact
from agent.services.prompts import (
    MAP_SYSTEM_PROMPT,
    MAP_USER_PROMPT,
    REDUCE_SYSTEM_PROMPT,
    REDUCE_USER_PROMPT
)
from transcripts.models import Transcript
from transcripts.services.chunking import get_or_create_chunks, estimate_tokens


# Constants
MODEL = getattr(settings, 'SUMMARIZE_MODEL', 'gpt-4o-mini')
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


def _map_chunk(chunk_text: str, client: OpenAI) -> dict:
    """
    Summarize a single chunk using the map prompt.
    
    Args:
        chunk_text: Text content of the chunk
        client: OpenAI client instance
        
    Returns:
        Dict with keys: bullets (list), mentions_guidance (bool)
        
    Raises:
        ValueError: If response JSON is invalid after retry
        Exception: For OpenAI API errors
    """
    user_prompt = MAP_USER_PROMPT.format(chunk_text=chunk_text)
    
    # First attempt
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": MAP_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content
        return _parse_json_response(result_text, "map phase")
        
    except ValueError as e:
        # Retry once with stricter prompt
        retry_prompt = user_prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no explanations."
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": MAP_SYSTEM_PROMPT},
                {"role": "user", "content": retry_prompt}
            ],
            temperature=0.1,
            max_tokens=500
        )
        
        result_text = response.choices[0].message.content
        return _parse_json_response(result_text, "map phase retry")


def _reduce(map_outputs: List[dict], client: OpenAI) -> dict:
    """
    Merge multiple chunk summaries into a final summary.
    
    Args:
        map_outputs: List of dicts from _map_chunk
        client: OpenAI client instance
        
    Returns:
        Dict with keys: bullets (list), sections_covered (list)
        
    Raises:
        ValueError: If response JSON is invalid after retry
        Exception: For OpenAI API errors
    """
    # Format summaries for the reduce prompt
    summaries_text = ""
    for i, output in enumerate(map_outputs):
        summaries_text += f"\n--- Summary {i+1} ---\n"
        for bullet in output.get("bullets", []):
            summaries_text += f"• {bullet}\n"
    
    user_prompt = REDUCE_USER_PROMPT.format(summaries=summaries_text)
    
    # First attempt
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": REDUCE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=800
        )
        
        result_text = response.choices[0].message.content
        return _parse_json_response(result_text, "reduce phase")
        
    except ValueError as e:
        # Retry once with stricter prompt
        retry_prompt = user_prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No markdown, no explanations."
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": REDUCE_SYSTEM_PROMPT},
                {"role": "user", "content": retry_prompt}
            ],
            temperature=0.1,
            max_tokens=800
        )
        
        result_text = response.choices[0].message.content
        return _parse_json_response(result_text, "reduce phase retry")


def get_or_create_summary(transcript: Transcript) -> Tuple[Artifact, bool]:
    """
    Get cached summary or create a new one using map/reduce.
    
    Process:
    1. Check if artifact exists in cache
    2. If not, get chunks from transcript
    3. Validate chunk token counts (relies on Phase 3 chunking limits)
    4. Map: Summarize each chunk (parallelized)
    5. Reduce: Merge summaries
    6. Persist artifact
    
    Args:
        transcript: Transcript instance to summarize
        
    Returns:
        Tuple of (Artifact instance, was_cached: bool)
        
    Raises:
        Exception: For OpenAI API errors or invalid responses
    """
    # Check cache
    try:
        artifact = Artifact.objects.get(
            transcript=transcript,
            artifact_type="summary",
            model=MODEL,
            prompt_version=PROMPT_VERSION
        )
        return artifact, True
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
                f"This indicates a Phase 3 chunking failure."
            )
    
    # Map phase: Summarize each chunk (parallelized)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Create a helper function that includes the client
        def summarize_chunk(chunk):
            return _map_chunk(chunk.text, client)
        
        # Map all chunks in parallel
        map_outputs = list(executor.map(summarize_chunk, chunks))
    
    # Reduce phase: Merge summaries with hierarchical reduction if needed
    # Estimate tokens in reduce input
    reduce_input_text = json.dumps(map_outputs)
    reduce_tokens = len(reduce_input_text) // 4  
    
    if reduce_tokens > MAX_REDUCE_TOKENS:
        # Hierarchical reduce: batch reduce, then final reduce
        batch_size = 20
        batch_summaries = []
        
        for i in range(0, len(map_outputs), batch_size):
            batch = map_outputs[i:i+batch_size]
            batch_summary = _reduce(batch, client)
            batch_summaries.append(batch_summary)
        
        # Final reduce of batch summaries
        final_summary = _reduce(batch_summaries, client)
    else:
        # Direct reduce
        final_summary = _reduce(map_outputs, client)
    
    # Persist artifact
    artifact = Artifact.objects.create(
        transcript=transcript,
        artifact_type="summary",
        model=MODEL,
        prompt_version=PROMPT_VERSION,
        content=final_summary
    )
    
    return artifact, False
