"""
Chat orchestrator service.

Handles conversation flow, intent detection, and routing to appropriate services.
"""

import logging
import re
from typing import Dict, Optional, Tuple

from django.db import transaction
from django.db.models import Max

from agent.services.extract import get_or_create_extraction
from agent.services.formatting import format_artifact_content
from agent.services.qa import answer_question
from agent.services.summarize import get_or_create_summary
from chat.models import Conversation, Message
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
        Intent string: 'fetch', 'summarize', 'extract', or 'qa'
    """
    lower = message.lower()
    
    # Check for fetch intent
    if any(word in lower for word in ["fetch", "get transcript", "load", "retrieve transcript"]):
        return "fetch"
    
    # Check for summarize intent
    if any(word in lower for word in ["summarize", "summary", "give me a summary"]):
        return "summarize"
    
    # Check for extract intent
    if any(word in lower for word in ["extract", "metrics", "guidance", "risks", "key numbers"]):
        return "extract"
    
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
    - Intent detection
    - Symbol/quarter extraction
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
    
    # Detect intent
    intent = detect_intent(user_message)
    logger.info(f"Detected intent: {intent} for message: {user_message[:50]}...")
    
    # Initialize response
    assistant_message = ""
    citations = None
    needs_clarification = False
    
    # Process based on intent
    if intent in ['fetch', 'summarize', 'extract']:
        # These intents need a transcript
        if conversation.current_transcript:
            # Already have a transcript, use it
            transcript = conversation.current_transcript
            
            if intent == 'fetch':
                assistant_message = (
                    f"I already have the transcript for {transcript.symbol} {transcript.quarter}. "
                    f"You can ask me to summarize it, extract key information, or ask specific questions."
                )
            elif intent == 'summarize':
                summary_artifact, was_cached = get_or_create_summary(transcript)
                cached_status = " (from cache)" if was_cached else ""
                formatted_content = format_artifact_content('summary', summary_artifact.content)
                assistant_message = f"Here's the summary for {transcript.symbol} {transcript.quarter}{cached_status}:\n\n{formatted_content}"
            elif intent == 'extract':
                extraction_artifact, was_cached = get_or_create_extraction(transcript)
                cached_status = " (from cache)" if was_cached else ""
                formatted_content = format_artifact_content('extraction', extraction_artifact.content)
                assistant_message = f"Here are the extracted key metrics and information for {transcript.symbol} {transcript.quarter}{cached_status}:\n\n{formatted_content}"
        else:
            # Need to fetch transcript
            symbol, quarter = extract_symbol_quarter(user_message)
            
            if not symbol or not quarter:
                # Missing information, ask for clarification
                needs_clarification = True
                missing = []
                if not symbol:
                    missing.append("ticker symbol")
                if not quarter:
                    missing.append("quarter (e.g., 'Q1 2024' or '2024Q1')")
                assistant_message = f"I need the {' and '.join(missing)} to fetch the transcript. Please provide it in your message."
            else:
                # Fetch the transcript
                try:
                    transcript = get_or_fetch_transcript(symbol, quarter)
                    
                    # Update conversation with current transcript
                    conversation.current_transcript = transcript
                    conversation.save()
                    
                    if intent == 'fetch':
                        assistant_message = f"Successfully fetched transcript for {symbol} {quarter}. You can now ask me to summarize it, extract key information, or ask specific questions."
                    elif intent == 'summarize':
                        summary_artifact, was_cached = get_or_create_summary(transcript)
                        formatted_content = format_artifact_content('summary', summary_artifact.content)
                        assistant_message = f"Here's the summary for {symbol} {quarter}:\n\n{formatted_content}"
                    elif intent == 'extract':
                        extraction_artifact, was_cached = get_or_create_extraction(transcript)
                        formatted_content = format_artifact_content('extraction', extraction_artifact.content)
                        assistant_message = f"Here are the extracted key metrics and information for {symbol} {quarter}:\n\n{formatted_content}"
                        
                except TranscriptNotAvailable as e:
                    raise
                except RateLimitError as e:
                    raise
    
    elif intent == 'qa':
        # Q&A intent
        if not conversation.current_transcript:
            # Need a transcript for Q&A
            needs_clarification = True
            assistant_message = "I need a transcript to answer questions. Please specify a ticker symbol and quarter (e.g., 'AAPL Q1 2024') or ask me to fetch one first."
        else:
            # Answer the question
            transcript = conversation.current_transcript
            result = answer_question(transcript, user_message)
            assistant_message = result['answer']
            citations = result.get('citations', [])
    
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
            citations=citations,
            message_index=next_index
        )
    
    return {
        'conversation_id': str(conversation.id),
        'assistant_message': assistant_message,
        'citations': citations,
        'intent': intent,
        'needs_clarification': needs_clarification
    }
