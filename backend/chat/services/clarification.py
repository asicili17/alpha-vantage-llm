"""
Clarification service for handling underspecified user requests.

Makes the system ask targeted follow-up questions instead of guessing.
"""

import logging
from typing import Optional, List, Dict

from chat.services.query_schema import ParsedQuery
from chat.services.query_logging import log_clarification_triggered


logger = logging.getLogger(__name__)


def generate_clarification_response(
    parsed_query: ParsedQuery,
    conversation_context: Optional[Dict] = None
) -> Dict:
    """
    Generate a clarification response for an underspecified query.
    
    Args:
        parsed_query: Parsed query with needs_clarification=True
        conversation_context: Optional context for smarter clarification
    
    Returns:
        Dict with assistant_message and needs_clarification=True
    """
    if not parsed_query.needs_clarification:
        logger.warning("generate_clarification_response called on query that doesn't need clarification")
        return {
            'assistant_message': "I can help you with that. What would you like to know?",
            'needs_clarification': False
        }
    
    # Use the pre-generated clarification message from query understanding
    if parsed_query.clarification_message:
        message = parsed_query.clarification_message
    else:
        # Fallback generic clarification
        message = _generate_generic_clarification(parsed_query)
    
    # Log clarification trigger
    log_clarification_triggered(
        raw_input=parsed_query.raw_input,
        missing_fields=parsed_query.missing_fields or [],
        clarification_message=message
    )
    
    return {
        'assistant_message': message,
        'needs_clarification': True,
        'intent': parsed_query.intent,
        'missing_fields': parsed_query.missing_fields
    }


def _generate_generic_clarification(parsed_query: ParsedQuery) -> str:
    """Generate generic clarification message based on intent."""
    if parsed_query.intent in ['fetch', 'summarize']:
        return "I need a ticker symbol and quarter to fetch the transcript. Please provide them (e.g., 'AAPL Q1 2024')."
    elif parsed_query.intent == 'qa':
        return "I need a transcript to answer questions. Please specify a ticker symbol and quarter, or ask me to fetch one first."
    else:
        return "I need more information to help you. Could you provide more details?"


def is_clarification_complete(
    new_query: ParsedQuery,
    previous_missing_fields: List[str]
) -> bool:
    """
    Check if a new query completes a previous clarification.
    
    Args:
        new_query: New parsed query
        previous_missing_fields: Fields that were missing before
    
    Returns:
        True if all previously missing fields are now present
    """
    if not previous_missing_fields:
        return True
    
    for field in previous_missing_fields:
        if field == 'symbol' and not new_query.symbol:
            return False
        if field == 'quarter' and not new_query.quarter:
            return False
    
    return True


def should_clarify_instead_of_answer(
    parsed_query: ParsedQuery,
    has_active_transcript: bool,
    retrieval_quality: Optional[str] = None
) -> bool:
    """
    Decide whether to clarify instead of attempting an answer.
    
    Used in retrieval quality gating (Phase 5).
    
    Args:
        parsed_query: Parsed query
        has_active_transcript: Whether conversation has active transcript
        retrieval_quality: Optional quality signal ('high', 'medium', 'low')
    
    Returns:
        True if clarification is better than a weak answer
    """
    # If query already needs clarification, yes
    if parsed_query.needs_clarification:
        return True
    
    # If retrieval quality is low and scope is ambiguous
    if retrieval_quality == 'low':
        # Check if scope could be tightened
        if not parsed_query.requested_section and not parsed_query.topic:
            return True
    
    # If no transcript and query doesn't provide scope
    if not has_active_transcript:
        if not parsed_query.is_complete_for_fetch():
            return True
    
    return False
