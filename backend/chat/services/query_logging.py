"""
Basic logging for query understanding and clarification events.

Lightweight logging to track:
- Parse failures (when validation fails)
- Clarification triggers (when user input is underspecified)
- Filter applications (section/speaker constraints)

For production, extend this to integrate with proper telemetry.
"""

import logging
from typing import Dict, Optional
from datetime import datetime


logger = logging.getLogger(__name__)


class QueryUnderstandingLogger:
    """Logger for query understanding events."""
    
    @staticmethod
    def log_parse_attempt(raw_input: str, parsed_query: Dict):
        """Log a query parsing attempt."""
        logger.info(
            "Query parsed",
            extra={
                "event": "query_parsed",
                "raw_input": raw_input,
                "intent": parsed_query.get("intent"),
                "symbol": parsed_query.get("symbol"),
                "quarter": parsed_query.get("quarter"),
                "needs_clarification": parsed_query.get("needs_clarification"),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_parse_failure(raw_input: str, reason: str):
        """Log a parsing failure."""
        logger.warning(
            "Query parse failed",
            extra={
                "event": "parse_failure",
                "raw_input": raw_input,
                "reason": reason,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_clarification_triggered(
        raw_input: str, 
        missing_fields: list, 
        clarification_message: str
    ):
        """Log when clarification is triggered."""
        logger.info(
            "Clarification triggered",
            extra={
                "event": "clarification_triggered",
                "raw_input": raw_input,
                "missing_fields": missing_fields,
                "clarification_message": clarification_message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_filter_application(
        section_filter: Optional[str] = None,
        speaker_filter: Optional[str] = None,
        chunks_before: int = 0,
        chunks_after: int = 0
    ):
        """Log application of metadata filters."""
        logger.info(
            "Filters applied to retrieval",
            extra={
                "event": "filter_application",
                "section_filter": section_filter,
                "speaker_filter": speaker_filter,
                "chunks_before_filter": chunks_before,
                "chunks_after_filter": chunks_after,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_retrieval_quality_gate(
        chunks_retrieved: int,
        threshold: int,
        quality: str,
        query: str
    ):
        """Log retrieval quality gate evaluation."""
        logger.info(
            "Retrieval quality evaluated",
            extra={
                "event": "retrieval_quality_gate",
                "chunks_retrieved": chunks_retrieved,
                "min_threshold": threshold,
                "quality_assessment": quality,
                "query": query,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    @staticmethod
    def log_session_context_usage(
        had_context: bool,
        symbol_from_context: Optional[str] = None,
        quarter_from_context: Optional[str] = None
    ):
        """Log when session context is used to resolve query."""
        logger.info(
            "Session context used",
            extra={
                "event": "session_context_usage",
                "had_context": had_context,
                "symbol_from_context": symbol_from_context,
                "quarter_from_context": quarter_from_context,
                "timestamp": datetime.utcnow().isoformat()
            }
        )


# Convenience functions
def log_parse_attempt(raw_input: str, parsed_query: Dict):
    """Log a query parsing attempt."""
    QueryUnderstandingLogger.log_parse_attempt(raw_input, parsed_query)


def log_parse_failure(raw_input: str, reason: str):
    """Log a parsing failure."""
    QueryUnderstandingLogger.log_parse_failure(raw_input, reason)


def log_clarification_triggered(
    raw_input: str, 
    missing_fields: list, 
    clarification_message: str
):
    """Log when clarification is triggered."""
    QueryUnderstandingLogger.log_clarification_triggered(
        raw_input, missing_fields, clarification_message
    )


def log_filter_application(
    section_filter: Optional[str] = None,
    speaker_filter: Optional[str] = None,
    chunks_before: int = 0,
    chunks_after: int = 0
):
    """Log application of metadata filters."""
    QueryUnderstandingLogger.log_filter_application(
        section_filter, speaker_filter, chunks_before, chunks_after
    )


def log_retrieval_quality_gate(
    chunks_retrieved: int,
    threshold: int,
    quality: str,
    query: str
):
    """Log retrieval quality gate evaluation."""
    QueryUnderstandingLogger.log_retrieval_quality_gate(
        chunks_retrieved, threshold, quality, query
    )


def log_session_context_usage(
    had_context: bool,
    symbol_from_context: Optional[str] = None,
    quarter_from_context: Optional[str] = None
):
    """Log when session context is used to resolve query."""
    QueryUnderstandingLogger.log_session_context_usage(
        had_context, symbol_from_context, quarter_from_context
    )
