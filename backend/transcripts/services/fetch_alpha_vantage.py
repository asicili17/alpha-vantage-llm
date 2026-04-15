"""
Alpha Vantage MCP client for fetching earnings call transcripts.

This service handles:
- MCP tool calls to Alpha Vantage
- Response normalization from structured turns to normalized text
- Caching logic
"""

from django.conf import settings


class AlphaVantageMCPClient:
    """Client for Alpha Vantage MCP transcript retrieval."""
    
    def __init__(self):
        self.api_key = settings.ALPHAVANTAGE_API_KEY
        self.transport = settings.ALPHAVANTAGE_MCP_TRANSPORT
        self.mcp_url = settings.ALPHAVANTAGE_MCP_URL
    
    def fetch_transcript(self, symbol: str, quarter: str) -> dict:
        """
        Fetch earnings call transcript from Alpha Vantage via MCP.
        
        Args:
            symbol: Stock ticker symbol (e.g., 'AAPL')
            quarter: Quarter in YYYYQ{1-4} format (e.g., '2024Q2')
        
        Returns:
            dict with keys: symbol, quarter, transcript (list of turns)
        
        Raises:
            ValueError: if parameters are invalid
            Exception: if MCP call fails
        """
        # TODO: Implement actual MCP client call
        # For now, this is a placeholder
        raise NotImplementedError("MCP client integration pending")
    
    def normalize_transcript(self, raw_response: dict) -> dict:
        """
        Normalize raw MCP response into usable format.
        
        Args:
            raw_response: Raw response from Alpha Vantage MCP
        
        Returns:
            dict with:
                - raw_text: concatenated speaker turns
                - normalized_text: formatted "Speaker (Title): content..."
                - turns: list of structured turn data
                - metadata: company name, call date, etc.
        """
        # TODO: Implement normalization logic based on actual API response
        raise NotImplementedError("Normalization logic pending")
