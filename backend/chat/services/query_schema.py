"""
Query schema for structured user request representation.

Defines the normalized query object that all user input should be parsed into.
"""

from dataclasses import dataclass
from typing import Optional, List


@dataclass
class ParsedQuery:
    """
    Structured representation of a normalized user request.
    
    This schema is the contract between query understanding and the rest
    of the system. All fields should be validated before routing/execution.
    """
    # Core intent
    intent: str  # 'fetch', 'summarize', 'qa', 'clarify'
    
    # Company/ticker scope
    symbol: Optional[str] = None  # Normalized ticker (e.g., 'AAPL')
    company_name: Optional[str] = None  # Company name if mentioned (e.g., 'Apple')
    
    # Time scope
    quarter: Optional[str] = None  # Normalized format: '2024Q1'
    relative_period: Optional[str] = None  # 'latest', 'last quarter', 'prior quarter'
    
    # Retrieval constraints
    requested_section: Optional[str] = None  # 'prepared', 'qa', None (both)
    requested_speaker: Optional[str] = None  # Speaker name or role
    topic: Optional[str] = None  # Topic/theme extracted from question
    
    # Advanced features (future)
    comparison_mode: bool = False  # Whether comparing multiple periods/companies
    
    # Clarification tracking
    needs_clarification: bool = False
    missing_fields: List[str] = None  # Fields that need clarification
    clarification_message: Optional[str] = None  # User-facing clarification prompt
    
    # Metadata
    confidence: str = 'high'  # 'high', 'medium', 'low'
    raw_input: str = ''  # Original user message
    
    def __post_init__(self):
        """Initialize mutable default values."""
        if self.missing_fields is None:
            self.missing_fields = []
    
    def is_complete_for_fetch(self) -> bool:
        """Check if query has enough info to fetch a transcript."""
        return self.symbol is not None and self.quarter is not None
    
    def is_complete_for_qa(self, has_active_transcript: bool) -> bool:
        """Check if query has enough info for Q&A."""
        return has_active_transcript or self.is_complete_for_fetch()
    
    def is_complete_for_summarize(self, has_active_transcript: bool) -> bool:
        """Check if query has enough info for summarization."""
        return has_active_transcript or self.is_complete_for_fetch()


# Valid intent values
VALID_INTENTS = {'fetch', 'summarize', 'qa', 'clarify'}

# Valid section values
VALID_SECTIONS = {'prepared', 'qa', None}

# Valid confidence values
VALID_CONFIDENCE = {'high', 'medium', 'low'}
