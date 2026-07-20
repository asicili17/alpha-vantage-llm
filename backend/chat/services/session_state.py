"""
Session state management for multi-turn conversation context.

Tracks resolved scope and helps interpret follow-up requests.
"""

from typing import Dict, Any, Optional
from chat.models import Conversation


def build_session_context(conversation: Conversation) -> Dict[str, Any]:
    """
    Build compact session context from conversation state.
    
    This context is passed to query understanding to help resolve
    follow-up questions and implicit references.
    
    Args:
        conversation: Conversation instance
    
    Returns:
        Dict with session context fields
    """
    context = {
        'has_active_transcript': conversation.current_transcript is not None,
    }
    
    # Add active transcript scope
    if conversation.current_transcript:
        context['last_resolved_symbol'] = conversation.current_transcript.symbol
        context['last_resolved_quarter'] = conversation.current_transcript.quarter
        context['active_transcript_id'] = str(conversation.current_transcript.id)
    
    # TODO: Add from extended conversation fields when Phase 2 migrations complete
    # context['last_requested_section'] = conversation.last_requested_section
    # context['last_topic'] = conversation.last_topic
    # context['pending_clarification_fields'] = conversation.pending_clarification_fields
    
    return context


def update_session_context_from_query(
    conversation: Conversation,
    parsed_query: 'ParsedQuery'
) -> None:
    """
    Update conversation state based on successfully parsed query.
    
    This is called after a query is successfully executed to update
    the session context for future follow-ups.
    
    Args:
        conversation: Conversation to update
        parsed_query: The successfully executed query
    """
    # For now, current_transcript is updated in the main orchestrator
    # Future: update additional session fields here
    
    # TODO: When Phase 2 migrations are complete, persist:
    # if parsed_query.symbol:
    #     conversation.last_resolved_symbol = parsed_query.symbol
    # if parsed_query.quarter:
    #     conversation.last_resolved_quarter = parsed_query.quarter
    # if parsed_query.requested_section:
    #     conversation.last_requested_section = parsed_query.requested_section
    # if parsed_query.topic:
    #     conversation.last_topic = parsed_query.topic
    
    pass


def should_carry_forward_context(
    parsed_query: 'ParsedQuery',
    session_context: Dict[str, Any]
) -> bool:
    """
    Decide whether to carry forward session context for a query.
    
    Rule: Explicit user mentions always override stored context.
    
    Args:
        parsed_query: Parsed query
        session_context: Current session context
    
    Returns:
        True if context should be used, False if user intent overrides
    """
    # If query has explicit scope, that takes precedence
    if parsed_query.symbol or parsed_query.quarter:
        return False
    
    # If confidence is low, prefer clarification over guess
    if parsed_query.confidence == 'low':
        return False
    
    # Otherwise allow context carry-forward
    return True
