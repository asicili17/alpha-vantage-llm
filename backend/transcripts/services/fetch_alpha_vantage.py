"""
Alpha Vantage REST API client for fetching earnings call transcripts.

This service handles:
- Direct REST API calls to Alpha Vantage
- Response normalization from structured turns to normalized text
- Caching logic
"""

import json
import logging
import re

import httpx
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from transcripts.models import Transcript, TranscriptTurn
from transcripts.services.chunking import get_or_create_chunks

logger = logging.getLogger(__name__)


class TranscriptNotAvailable(Exception):
    """Raised when transcript is not available for the given symbol/quarter."""
    pass


class RateLimitError(Exception):
    """Raised when Alpha Vantage API rate limit is exceeded."""
    pass


class AlphaVantageRestClient:
    """Client for Alpha Vantage REST API transcript retrieval."""
    
    def __init__(self):
        self.base_url = "https://www.alphavantage.co/query"
        self.api_key = settings.ALPHAVANTAGE_API_KEY
    
    def fetch_transcript(self, symbol: str, quarter: str) -> dict:
        """
        Fetch earnings call transcript from Alpha Vantage REST API.
        
        Note: This method returns the raw JSON payload from Alpha Vantage.
        It does NOT normalize the turns. For normalized turn access, use
        get_or_fetch_transcript() which returns a Transcript model with
        the .turns relationship populated.
        
        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')
            quarter: Quarter in YYYYQ{1-4} format (e.g., '2024Q2')
        
        Returns:
            dict: Raw Alpha Vantage payload with keys:
                  - symbol: str
                  - quarter: str
                  - transcript: list[dict] (raw turn data)
                  - company_name: str (optional)
        
        Raises:
            ValueError: if parameters are invalid
            TranscriptNotAvailable: if transcript not found
            RateLimitError: if rate limit exceeded
        """
        # Validate inputs
        if not re.match(r'^[A-Z]{1,5}$', symbol):
            raise ValueError(f"Invalid symbol format: {symbol}")
        if not re.match(r'^\d{4}Q[1-4]$', quarter):
            raise ValueError(f"Invalid quarter format: {quarter}")
        
        # Call Alpha Vantage REST API directly
        try:
            response = httpx.get(
                self.base_url,
                params={
                    "function": "EARNINGS_CALL_TRANSCRIPT",
                    "symbol": symbol,
                    "quarter": quarter,
                    "apikey": self.api_key
                },
                timeout=30
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(f"Alpha Vantage API HTTP error {e.response.status_code}: {e.response.text[:500]}")
            raise
        except httpx.HTTPError as e:
            logger.error(f"Alpha Vantage API request failed: {type(e).__name__}: {str(e)}")
            raise
        
        # Parse JSON response
        try:
            payload = response.json()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {str(e)}")
            raise RuntimeError(f"Invalid JSON response from Alpha Vantage API")
        
        # Check for Alpha Vantage error conditions
        if "Note" in payload:
            raise RateLimitError(payload["Note"])
        
        if "Error Message" in payload:
            raise ValueError(payload["Error Message"])
        
        if "transcript" not in payload:
            raise TranscriptNotAvailable(f"No transcript data for {symbol} {quarter}")
        
        return payload


def _normalize_turns(raw_payload: dict) -> list[dict]:
    """
    Convert raw transcript array to normalized turn list.
    
    Args:
        raw_payload: Raw Alpha Vantage response with 'transcript' key
    
    Returns:
        List of dicts with keys: turn_index, speaker, title, content, sentiment
    
    Raises:
        TranscriptNotAvailable: if transcript array is missing or empty
    """
    transcript_array = raw_payload.get("transcript", [])
    
    # Check for empty transcript array
    if not transcript_array:
        raise TranscriptNotAvailable(
            f"Transcript array is empty for {raw_payload.get('symbol', 'unknown')}"
        )
    
    normalized = []
    
    for idx, turn in enumerate(transcript_array):
        # Parse sentiment as float or None
        sentiment = turn.get("sentiment")
        if sentiment is not None:
            try:
                sentiment = float(sentiment)
            except (ValueError, TypeError):
                sentiment = None
        
        normalized.append({
            "turn_index": idx,
            "speaker": turn.get("speaker", "Unknown"),
            "title": turn.get("title"),
            "content": turn.get("content", ""),
            "sentiment": sentiment
        })
    
    return normalized


def get_or_fetch_transcript(symbol: str, quarter: str) -> Transcript:
    """
    Get transcript from cache or fetch from Alpha Vantage.
    
    This is the main entry point for transcript retrieval. It handles
    caching, fetching, normalization, and database storage.
    
    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL')
        quarter: Quarter in YYYYQ{1-4} format (e.g., '2024Q2')
    
    Returns:
        Transcript: Django model instance with the following accessible data:
                   - .symbol, .quarter, .source metadata
                   - .raw_text, .normalized_text for full transcript text
                   - .turns relationship for accessing normalized turn-by-turn data
                     (query with transcript.turns.all() to get TranscriptTurn objects)
    
    Raises:
        ValueError: if inputs are invalid
        TranscriptNotAvailable: if transcript not found
        RateLimitError: if rate limit exceeded
    """
    # Try DB cache first
    try:
        transcript = Transcript.objects.get(
            source="alphavantage",
            symbol=symbol,
            quarter=quarter
        )
        # Ensure chunks exist for cached transcript
        get_or_create_chunks(transcript)
        return transcript
    except Transcript.DoesNotExist:
        pass
    
    # Fetch from Alpha Vantage
    client = AlphaVantageRestClient()
    raw_payload = client.fetch_transcript(symbol, quarter)
    
    # Normalize turns
    normalized_turns = _normalize_turns(raw_payload)
    
    # Build raw_text and normalized_text
    raw_text_parts = []
    normalized_text_parts = []
    
    for turn in normalized_turns:
        raw_text_parts.append(turn["content"])
        
        speaker = turn["speaker"]
        title = turn.get("title")
        content = turn["content"]
        
        if title:
            normalized_text_parts.append(f"{speaker} ({title}): {content}")
        else:
            normalized_text_parts.append(f"{speaker}: {content}")
    
    raw_text = "\n\n".join(raw_text_parts)
    normalized_text = "\n\n".join(normalized_text_parts)
    
    # Create Transcript record with concurrency handling
    try:
        with transaction.atomic():
            transcript = Transcript.objects.create(
                symbol=symbol,
                quarter=quarter,
                source="alphavantage",
                raw_payload=raw_payload,
                raw_text=raw_text,
                normalized_text=normalized_text,
                fetched_at=timezone.now(),
                company_name=raw_payload.get("company_name")
            )
            
            # Create TranscriptTurn records
            turn_objects = [
                TranscriptTurn(
                    transcript=transcript,
                    turn_index=turn["turn_index"],
                    speaker=turn["speaker"],
                    title=turn.get("title"),
                    content=turn["content"],
                    sentiment=turn.get("sentiment")
                )
                for turn in normalized_turns
            ]
            TranscriptTurn.objects.bulk_create(turn_objects)
    
    except IntegrityError:
        # Another request created the same transcript concurrently
        # Retry the DB lookup
        transcript = Transcript.objects.get(
            source="alphavantage",
            symbol=symbol,
            quarter=quarter
        )
    
    # Create chunks immediately
    get_or_create_chunks(transcript)
    
    return transcript
