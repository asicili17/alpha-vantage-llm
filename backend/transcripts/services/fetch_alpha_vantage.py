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
from datetime import date, timedelta
from typing import Optional

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
        
        # Log the payload structure for debugging
        logger.debug(f"Alpha Vantage response for {symbol} {quarter}: keys={list(payload.keys())}, transcript_length={len(payload.get('transcript', []))}")
        
        # Check for information messages (often rate limiting or data availability)
        if "Information" in payload:
            info_msg = payload["Information"]
            logger.warning(f"Alpha Vantage Information for {symbol} {quarter}: {info_msg}")
            # Treat information messages as temporary unavailability
            raise TranscriptNotAvailable(f"Alpha Vantage Info: {info_msg}")
        
        # Check for Alpha Vantage error conditions
        if "Note" in payload:
            raise RateLimitError(payload["Note"])
        
        if "Error Message" in payload:
            raise ValueError(payload["Error Message"])
        
        if "transcript" not in payload:
            logger.warning(f"No 'transcript' key in payload for {symbol} {quarter}")
            raise TranscriptNotAvailable(f"No transcript data for {symbol} {quarter}")
        
        # Check if transcript array is empty (unavailable transcript)
        transcript_array = payload.get("transcript", [])
        if not transcript_array or len(transcript_array) == 0:
            logger.warning(f"Empty transcript array for {symbol} {quarter}")
            raise TranscriptNotAvailable(f"No transcript data for {symbol} {quarter}")
        
        logger.debug(f"Valid transcript found for {symbol} {quarter} with {len(transcript_array)} turns")
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


# =============================================================================
# Entity Resolution Functions (Phase 4)
# =============================================================================

def resolve_company_name_to_symbol(company_name: str) -> Optional[str]:
    """
    Resolve company name to ticker symbol using Alpha Vantage SYMBOL_SEARCH.
    
    Uses deterministic rules:
    - Accept top match only when type=='Equity'
    - Require minimum match score (0.8)
    - Do not filter by region
    
    Args:
        company_name: Company name to resolve (e.g., "Apple", "Microsoft")
    
    Returns:
        Ticker symbol (e.g., "AAPL") or None if cannot resolve confidently
    """
    if not company_name:
        return None
    
    try:
        response = httpx.get(
            "https://www.alphavantage.co/query",
            params={
                "function": "SYMBOL_SEARCH",
                "keywords": company_name,
                "apikey": settings.ALPHAVANTAGE_API_KEY
            },
            timeout=10
        )
        response.raise_for_status()
        
        payload = response.json()
        
        # Check for API errors
        if "Note" in payload:
            logger.warning(f"Alpha Vantage rate limit hit during symbol search")
            return None
        
        if "Error Message" in payload:
            logger.warning(f"Alpha Vantage error during symbol search: {payload['Error Message']}")
            return None
        
        best_matches = payload.get("bestMatches", [])
        
        if not best_matches:
            logger.info(f"No symbol matches found for '{company_name}'")
            return None
        
        # Get top match
        top_match = best_matches[0]
        
        # Validate match criteria
        match_type = top_match.get("3. type", "")
        match_score = float(top_match.get("9. matchScore", "0.0"))
        symbol = top_match.get("1. symbol", "")
        
        # Require Equity type
        if match_type != "Equity":
            logger.info(f"Top match for '{company_name}' is not Equity type: {match_type}")
            return None
        
        # Require minimum match score
        if match_score < 0.8:
            logger.info(f"Top match score {match_score} below threshold for '{company_name}'")
            return None
        
        logger.info(f"Resolved '{company_name}' -> {symbol} (score: {match_score})")
        return symbol
        
    except httpx.HTTPError as e:
        logger.error(f"Symbol search HTTP error: {e}")
        return None
    except (ValueError, KeyError) as e:
        logger.error(f"Symbol search parsing error: {e}")
        return None


def resolve_latest_quarter_for_symbol(
    symbol: str,
    max_quarters_back: int = 8
) -> Optional[str]:
    """
    Resolve 'latest' to a concrete quarter by probing transcript availability.
    
    Generates candidate quarters from current date and probes in descending
    recency order until finding an available transcript.
    
    Args:
        symbol: Ticker symbol (e.g., "AAPL")
        max_quarters_back: Maximum quarters to probe (default 8, ~2 years back)
    
    Returns:
        Quarter in YYYYQN format (e.g., "2024Q2") or None if none found
    """
    if not symbol:
        return None
    
    # Generate candidate quarters from current date
    candidates = _generate_candidate_quarters(max_quarters_back)
    
    logger.info(f"Probing for latest quarter for {symbol} in: {candidates}")
    
    # Probe each candidate from newest to oldest
    for quarter in candidates:
        # First check database
        try:
            transcript = Transcript.objects.get(
                source="alphavantage",
                symbol=symbol,
                quarter=quarter
            )
            logger.info(f"Found cached transcript for {symbol} {quarter}")
            return quarter
        except Transcript.DoesNotExist:
            pass
        
        # Try fetching from Alpha Vantage and cache it
        try:
            # Use get_or_fetch_transcript to fetch AND cache in one call
            # This avoids hitting the API twice (once during probing, once during actual use)
            get_or_fetch_transcript(symbol, quarter)
            logger.info(f"Found available transcript for {symbol} {quarter}")
            return quarter
        except TranscriptNotAvailable:
            logger.debug(f"No transcript for {symbol} {quarter}")
            continue
        except RateLimitError:
            logger.warning(f"Rate limit hit while probing {symbol} {quarter}")
            break
        except Exception as e:
            logger.warning(f"Error probing {symbol} {quarter}: {e}")
            continue
    
    logger.warning(f"Could not find any recent transcript for {symbol}")
    return None


def _generate_candidate_quarters(count: int) -> list[str]:
    """
    Generate list of recent quarters in YYYYQN format, newest first.
    
    Args:
        count: Number of quarters to generate
    
    Returns:
        List of quarters like ["2024Q2", "2024Q1", "2023Q4", ...]
    """
    today = date.today()
    year = today.year
    month = today.month
    
    # Determine current quarter
    if month <= 3:
        quarter = 1
    elif month <= 6:
        quarter = 2
    elif month <= 9:
        quarter = 3
    else:
        quarter = 4
    
    candidates = []
    
    for i in range(count):
        candidates.append(f"{year}Q{quarter}")
        
        # Move to previous quarter
        quarter -= 1
        if quarter < 1:
            quarter = 4
            year -= 1
    
    return candidates
