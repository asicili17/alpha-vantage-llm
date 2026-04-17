"""
Alpha Vantage MCP client for fetching earnings call transcripts.

This service handles:
- MCP tool calls to Alpha Vantage
- Response normalization from structured turns to normalized text
- Caching logic
"""

import json
import re

import httpx
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from transcripts.models import Transcript, TranscriptTurn


class TranscriptNotAvailable(Exception):
    """Raised when transcript is not available for the given symbol/quarter."""
    pass


class RateLimitError(Exception):
    """Raised when Alpha Vantage API rate limit is exceeded."""
    pass


class AlphaVantageMcpClient:
    """Client for Alpha Vantage MCP transcript retrieval."""
    
    def __init__(self):
        self.base_url = settings.ALPHAVANTAGE_MCP_URL
        self.api_key = settings.ALPHAVANTAGE_API_KEY
    
    def _mcp_url(self) -> str:
        """Construct MCP URL with API key."""
        return f"{self.base_url}?apikey={self.api_key}"
    
    def _post(self, method: str, params: dict, call_id: int = 1) -> dict:
        """
        Make JSON-RPC POST request to MCP server.
        
        Args:
            method: JSON-RPC method name
            params: Parameters for the method
            call_id: JSON-RPC call ID
        
        Returns:
            Result portion of JSON-RPC response
        
        Raises:
            RuntimeError: if MCP returns error response
            httpx.HTTPError: if HTTP request fails
        """
        body = {
            "jsonrpc": "2.0",
            "id": call_id,
            "method": method,
            "params": params
        }
        
        response = httpx.post(self._mcp_url(), json=body, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        if "error" in data:
            raise RuntimeError(f"MCP error: {data['error']}")
        
        return data.get("result", {})
    
    def fetch_transcript(self, symbol: str, quarter: str) -> dict:
        """
        Fetch earnings call transcript from Alpha Vantage via MCP.
        
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
        
        # TODO: For future optimization, consider calling TOOL_GET first to
        # retrieve and cache the schema for EARNINGS_CALL_TRANSCRIPT. This
        # would enable validation and can be skipped on repeat calls.
        # See phase 2 plan for details.
        
        # Call TOOL_CALL with EARNINGS_CALL_TRANSCRIPT
        result = self._post(
            method="tools/call",
            params={
                "name": "TOOL_CALL",
                "arguments": {
                    "tool_name": "EARNINGS_CALL_TRANSCRIPT",
                    "arguments": {
                        "symbol": symbol,
                        "quarter": quarter
                    }
                }
            },
            call_id=2
        )
        
        # Extract content from MCP response
        # MCP returns: {"content": [{"type": "text", "text": "...json..."}]}
        if not result or "content" not in result:
            raise TranscriptNotAvailable(f"No content in MCP response for {symbol} {quarter}")
        
        content_items = result.get("content", [])
        if not content_items:
            raise TranscriptNotAvailable(f"Empty content for {symbol} {quarter}")
        
        # Get the text from first content item
        text_content = content_items[0].get("text", "")
        if not text_content:
            raise TranscriptNotAvailable(f"No text in content for {symbol} {quarter}")
        
        # Parse JSON from text content
        try:
            payload = json.loads(text_content)
        except json.JSONDecodeError:
            raise RuntimeError(f"Failed to parse JSON from MCP response: {text_content[:200]}")
        
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
        return transcript
    except Transcript.DoesNotExist:
        pass
    
    # Fetch from Alpha Vantage
    client = AlphaVantageMcpClient()
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
    
    return transcript
