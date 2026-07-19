"""
Chat orchestrator service.

Handles conversation flow, query understanding, and routing to appropriate services.
"""

import logging
import re
from typing import Dict, Optional, Tuple

from django.db import transaction
from django.db.models import Max

from agent.services.formatting import format_artifact_content
from agent.services.qa import answer_question
from agent.services.summarize import get_or_create_summary
from chat.models import Conversation, Message
from chat.services.query_understanding import parse_query, validate_parsed_query
from chat.services.session_state import build_session_context, update_session_context_from_query
from chat.services.clarification import generate_clarification_response
from transcripts.models import Transcript
from transcripts.services.fetch_alpha_vantage import (
    get_or_fetch_transcript,
    TranscriptNotAvailable,
    RateLimitError
)

logger = logging.getLogger(__name__)


def detect_intent(message: str) -> str:
    """
    Detect user intent from message using simple keyword matching.
    
    Args:
        message: User's message text
        
    Returns:
        Intent string: 'fetch', 'summarize', or 'qa'
    """
    lower = message.lower()
    
    # Check for fetch intent
    if any(word in lower for word in ["fetch", "get transcript", "load", "retrieve transcript"]):
        return "fetch"
    
    # Check for summarize intent
    if any(word in lower for word in ["summarize", "summary", "give me a summary"]):
        return "summarize"
    
    # Default to Q&A
    return "qa"


def extract_symbol_quarter(message: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract ticker symbol and quarter from message.
    
    Args:
        message: User's message text
        
    Returns:
        Tuple of (symbol, quarter) where either can be None
        Quarter format: "2024Q1"
    """
    # Look for ticker (2-5 uppercase letters, word boundaries)
    symbol_match = re.search(r'\b([A-Z]{2,5})\b', message)
    symbol = symbol_match.group(1) if symbol_match else None
    
    # Look for quarter (Q1-Q4) and year (2020-2030)
    # Handles formats like "Q1 2024", "2024 Q1", "2024Q1", "Q1-2024"
    quarter_match = re.search(
        r'(Q[1-4])\s*[-]?\s*(\d{4})|(\d{4})\s*[-]?\s*(Q[1-4])',
        message,
        re.IGNORECASE
    )
    
    if quarter_match:
        if quarter_match.group(1):
            # Q1 2024 format
            quarter = f"{quarter_match.group(2)}{quarter_match.group(1).upper()}"
        else:
            # 2024 Q1 format
            quarter = f"{quarter_match.group(3)}{quarter_match.group(4).upper()}"
    else:
        quarter = None
    
    return symbol, quarter


def process_message(conversation_id: Optional[str], user_message: str) -> Dict:
    """
    Process a user message and generate a response.
    
    Handles:
    - Conversation creation/retrieval
    - Query understanding and parsing
    - Session context resolution
    - Routing to appropriate services
    - Message persistence
    
    Args:
        conversation_id: UUID of existing conversation, or None to create new
        user_message: User's message text
        
    Returns:
        Dict with keys:
            - conversation_id: UUID string
            - assistant_message: Response text
            - citations: List of citation dicts (for Q&A)
            - intent: Detected intent string
            - needs_clarification: Boolean indicating if more info needed
            
    Raises:
        ValueError: For invalid inputs
        TranscriptNotAvailable: When transcript doesn't exist
        RateLimitError: When Alpha Vantage API rate limit exceeded
    """
    # Get or create conversation
    with transaction.atomic():
        if conversation_id:
            try:
                conversation = Conversation.objects.select_for_update().get(id=conversation_id)
            except Conversation.DoesNotExist:
                raise ValueError(f"Conversation {conversation_id} not found")
        else:
            conversation = Conversation.objects.create()
        
        # Get next message index
        max_index = conversation.messages.aggregate(
            max_idx=Max('message_index')
        )['max_idx']
        next_index = (max_index + 1) if max_index is not None else 0
        
        # Save user message
        Message.objects.create(
            conversation=conversation,
            role='user',
            content=user_message,
            message_index=next_index
        )
    
    # Build session context for query understanding
    session_context = build_session_context(conversation)
    
    
    # Parse query using new understanding layer
    parsed_query = parse_query(user_message, session_context=session_context)
    
    # Validate parsed query
    if not validate_parsed_query(parsed_query):
        logger.error(f"Invalid parsed query for: {user_message[:50]}")
        # Fallback to legacy parsing
        parsed_query = _fallback_legacy_parse(user_message, session_context)
    
    # Check for clarification needs
    if parsed_query.needs_clarification:
        clarification_message = generate_clarification_response(parsed_query)
        
        # Save clarification message
        with transaction.atomic():
            conversation.refresh_from_db()
            max_index = conversation.messages.aggregate(
                max_idx=Max('message_index')
            )['max_idx']
            next_index = (max_index + 1) if max_index is not None else 0
            
            Message.objects.create(
                conversation=conversation,
                role='assistant',
                content=clarification_message,
                message_index=next_index
            )
        
        return {
            'conversation_id': str(conversation.id),
            'assistant_message': clarification_message,
            'citations': [],
            'intent': parsed_query.intent,
            'needs_clarification': True
        }
    
    # Execute parsed query
    assistant_message, citations, needs_clarification = _execute_parsed_query(
        parsed_query,
        conversation,
        session_context
    )
    
    # Update session context based on successful query execution
    if not needs_clarification:
        update_session_context_from_query(conversation, parsed_query)
    
    # Save assistant message
    with transaction.atomic():
        # Refresh conversation to get updated message_index
        conversation.refresh_from_db()
        max_index = conversation.messages.aggregate(
            max_idx=Max('message_index')
        )['max_idx']
        next_index = (max_index + 1) if max_index is not None else 0
        
        Message.objects.create(
            conversation=conversation,
            role='assistant',
            content=assistant_message,
            citations=citations or [],
            message_index=next_index
        )
    
    return {
        'conversation_id': str(conversation.id),
        'assistant_message': assistant_message,
        'citations': citations or [],
        'intent': parsed_query.intent,
        'needs_clarification': needs_clarification
    }




def _execute_parsed_query(parsed_query, conversation, session_context):
    """
    Execute a validated parsed query and return results.
    
    Returns:
        Tuple of (assistant_message, citations, needs_clarification)
    """
    intent = parsed_query.intent
    symbol = parsed_query.symbol
    quarter = parsed_query.quarter
    
    assistant_message = ""
    citations = None
    needs_clarification = False
    
    # Handle fetch and summarize intents
    if intent in ['fetch', 'summarize']:
        if conversation.current_transcript:
            # Already have a transcript
            transcript = conversation.current_transcript
            
            # Check if user is requesting a different transcript
            if symbol and quarter:
                if symbol != transcript.symbol or quarter != transcript.quarter:
                    # User wants a different transcript
                    try:
                        transcript = get_or_fetch_transcript(symbol, quarter)
                        conversation.current_transcript = transcript
                        conversation.save()
                    except (TranscriptNotAvailable, RateLimitError):
                        raise
            
            if intent == 'fetch':
                assistant_message = (
                    f"I already have the transcript for {transcript.symbol} {transcript.quarter}. "
                    f"You can ask me to summarize it or ask specific questions."
                )
            elif intent == 'summarize':
                summary_artifact, was_cached = get_or_create_summary(transcript)
                cached_status = " (from cache)" if was_cached else ""
                formatted_content = format_artifact_content('summary', summary_artifact.content)
                assistant_message = f"Here's the summary for {transcript.symbol} {transcript.quarter}{cached_status}:\n\n{formatted_content}"
        
        else:
            # Need to fetch transcript
            if symbol and quarter:
                try:
                    transcript = get_or_fetch_transcript(symbol, quarter)
                    
                    # Update conversation with current transcript
                    conversation.current_transcript = transcript
                    conversation.save()
                    
                    if intent == 'fetch':
                        assistant_message = f"Successfully fetched transcript for {symbol} {quarter}. You can now ask me to summarize it or ask specific questions."
                    elif intent == 'summarize':
                        summary_artifact, was_cached = get_or_create_summary(transcript)
                        formatted_content = format_artifact_content('summary', summary_artifact.content)
                        assistant_message = f"Here's the summary for {symbol} {quarter}:\n\n{formatted_content}"
                
                except (TranscriptNotAvailable, RateLimitError):
                    raise
            else:
                # This shouldn't happen if parsing worked correctly
                needs_clarification = True
                assistant_message = "I need a ticker symbol and quarter to fetch the transcript."
    
    elif intent == 'qa':
        # Q&A intent
        if conversation.current_transcript:
            transcript = conversation.current_transcript
            
            # Phase 4: Apply parsed filters (section, speaker) to retrieval
            result = answer_question(
                transcript, 
                parsed_query.raw_input,
                section_filter=parsed_query.requested_section,
                speaker_filter=parsed_query.requested_speaker
            )
            assistant_message = result['answer']
            citations = result.get('citations', [])
            
            # Phase 5: Check retrieval quality
            if result.get('retrieval_quality') == 'insufficient':
                needs_clarification = True
        else:
            # No active transcript
            needs_clarification = True
            assistant_message = "I need a transcript to answer questions. Please specify a ticker symbol and quarter, or ask me to fetch one first."
    
    return assistant_message, citations, needs_clarification


def _fallback_legacy_parse(user_message: str, session_context: dict):
    """
    Fallback to legacy parsing if new parser fails validation.
    
    Returns a ParsedQuery using the old detect_intent and extract_symbol_quarter logic.
    """
    from chat.services.query_schema import ParsedQuery
    
    intent = detect_intent(user_message)
    symbol, quarter = extract_symbol_quarter(user_message)
    
    # Use session context if available
    if not symbol and 'last_resolved_symbol' in session_context:
        symbol = session_context['last_resolved_symbol']
    if not quarter and 'last_resolved_quarter' in session_context:
        quarter = session_context['last_resolved_quarter']
    
    needs_clarification = False
    missing_fields = []
    
    if intent in ['fetch', 'summarize'] and not session_context.get('has_active_transcript'):
        if not symbol:
            needs_clarification = True
            missing_fields.append('symbol')
        if not quarter:
            needs_clarification = True
            missing_fields.append('quarter')
    
    return ParsedQuery(
        intent=intent,
        symbol=symbol,
        quarter=quarter,
        needs_clarification=needs_clarification,
        missing_fields=missing_fields,
        raw_input=user_message
    )