"""
Query understanding service.

Hybrid approach: deterministic extraction where reliable, 
model-assisted normalization for complex/messy phrasing.
"""

import json
import logging
import re
from typing import Optional, Dict, Any

from django.conf import settings
from openai import OpenAI

from chat.services.query_schema import ParsedQuery, VALID_INTENTS, VALID_SECTIONS, VALID_CONFIDENCE
from chat.services.query_logging import (
    log_parse_attempt,
    log_parse_failure,
    log_session_context_usage
)
from agent.services.prompts import QUERY_PARSER_SYSTEM_PROMPT, QUERY_PARSER_USER_PROMPT
from transcripts.services.fetch_alpha_vantage import (
    resolve_company_name_to_symbol,
    resolve_latest_quarter_for_symbol
)


logger = logging.getLogger(__name__)

# Parser configuration from settings
PARSER_MODEL = getattr(settings, 'QUERY_PARSER_MODEL', 'gpt-4o-mini')
PARSER_ENABLED = getattr(settings, 'QUERY_PARSER_ENABLED', True)

# Parser model setting
PARSER_MODEL = getattr(settings, 'QUERY_PARSER_MODEL', 'gpt-4o-mini')
PARSER_ENABLED = getattr(settings, 'QUERY_PARSER_ENABLED', True)


# Deterministic extraction patterns
SYMBOL_PATTERN = re.compile(r'\b([A-Z]{2,5})\b')
QUARTER_PATTERN = re.compile(
    r'(Q[1-4])\s*[-]?\s*(\d{4})|(\d{4})\s*[-]?\s*(Q[1-4])',
    re.IGNORECASE
)

# Intent keywords
FETCH_KEYWORDS = ['fetch', 'get transcript', 'load', 'retrieve transcript', 'pull']
SUMMARIZE_KEYWORDS = ['summarize', 'summary', 'give me a summary', 'overview']


def _extract_symbol_deterministic(text: str) -> Optional[str]:
    """Extract ticker symbol using regex."""
    match = SYMBOL_PATTERN.search(text)
    return match.group(1) if match else None


def _extract_quarter_deterministic(text: str) -> Optional[str]:
    """Extract quarter using regex. Returns normalized '2024Q1' format."""
    match = QUARTER_PATTERN.search(text)
    if not match:
        return None
    
    if match.group(1):
        # Q1 2024 format
        return f"{match.group(2)}{match.group(1).upper()}"
    else:
        # 2024 Q1 format
        return f"{match.group(3)}{match.group(4).upper()}"


def _detect_intent_deterministic(text: str) -> Optional[str]:
    """Detect intent using keyword matching."""
    lower = text.lower()
    
    # Check fetch keywords
    if any(kw in lower for kw in FETCH_KEYWORDS):
        return 'fetch'
    
    # Check summarize keywords
    if any(kw in lower for kw in SUMMARIZE_KEYWORDS):
        return 'summarize'
    
    # Default to qa for questions
    return 'qa'


def _extract_section_constraint(text: str) -> Optional[str]:
    """Extract section constraint from user input."""
    lower = text.lower()
    
    # Check for explicit Q&A section mentions
    if any(phrase in lower for phrase in ['q&a', 'q & a', 'question and answer', 'analyst questions']):
        return 'qa'
    
    # Check for prepared remarks mentions
    if any(phrase in lower for phrase in ['prepared remarks', 'prepared statement', 'opening remarks']):
        return 'prepared'
    
    return None


def _extract_speaker_constraint(text: str) -> Optional[str]:
    """Extract speaker constraint from user input."""
    lower = text.lower()
    
    # Common roles
    if 'cfo' in lower or 'chief financial officer' in lower:
        return 'CFO'
    if 'ceo' in lower or 'chief executive officer' in lower:
        return 'CEO'
    if 'analyst' in lower:
        return 'Analyst'
    
    return None


def _extract_topic(text: str) -> Optional[str]:
    """Extract topic from question text."""
    lower = text.lower()
    
    # Common earnings topics
    topics = {
        'guidance': ['guidance', 'outlook', 'forecast'],
        'margins': ['margin', 'margins', 'profitability'],
        'revenue': ['revenue', 'sales', 'top line'],
        'earnings': ['earnings', 'eps', 'profit'],
        'ai': ['ai', 'artificial intelligence', 'machine learning'],
    }
    
    for topic_name, keywords in topics.items():
        if any(kw in lower for kw in keywords):
            return topic_name
    
    return None


def parse_query_with_llm(
    user_message: str,
    session_context: Optional[Dict[str, Any]] = None
) -> Optional[ParsedQuery]:
    """
    Parse user message using LLM with structured output.
    
    Returns ParsedQuery on success, None on failure (to trigger fallback).
    """
    if session_context is None:
        session_context = {}
    
    try:
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        # Build prompt with session context
        has_active_transcript = session_context.get('has_active_transcript', False)
        last_symbol = session_context.get('last_resolved_symbol', 'none')
        last_quarter = session_context.get('last_resolved_quarter', 'none')
        
        user_prompt = QUERY_PARSER_USER_PROMPT.format(
            user_message=user_message,
            has_active_transcript=has_active_transcript,
            last_symbol=last_symbol,
            last_quarter=last_quarter
        )
        
        # Call OpenAI with response format for structured output
        response = client.chat.completions.create(
            model=PARSER_MODEL,
            messages=[
                {"role": "system", "content": QUERY_PARSER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.1,  # Low temperature for consistent parsing
            response_format={"type": "json_object"}
        )
        
        # Parse JSON response
        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        
        # Map to ParsedQuery
        query = ParsedQuery(
            intent=result.get('intent', 'qa'),
            symbol=result.get('symbol'),
            company_name=result.get('company_name'),
            quarter=result.get('quarter'),
            relative_period=result.get('relative_period'),
            requested_section=result.get('requested_section'),
            requested_speaker=result.get('requested_speaker'),
            topic=result.get('topic'),
            comparison_mode=False,
            needs_clarification=result.get('needs_clarification', False),
            missing_fields=result.get('missing_fields', []),
            clarification_message=None,  # Will be generated by clarification service
            confidence=result.get('confidence', 'medium'),
            raw_input=user_message
        )
        
        return query
        
    except json.JSONDecodeError as e:
        logger.error(f"LLM parser returned invalid JSON: {e}")
        log_parse_failure(user_message, f"Invalid JSON from LLM: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"LLM parser failed: {e}")
        log_parse_failure(user_message, f"LLM parser exception: {str(e)}")
        return None


def parse_query(
    user_message: str,
    session_context: Optional[Dict[str, Any]] = None,
    use_llm_fallback: bool = True
) -> ParsedQuery:
    """
    Parse user message into structured query object.
    
    Uses LLM-primary approach:
    - LLM semantic parsing as primary path
    - Deterministic fallback for LLM failures or explicit command syntax
    - Session context resolution after parsing
    - Clarification logic after all resolution
    
    Args:
        user_message: Raw user input
        session_context: Optional session state for context resolution
        use_llm_fallback: Whether to use LLM for parsing (default True)
    
    Returns:
        ParsedQuery instance
    """
    if session_context is None:
        session_context = {}
    
    query = None
    used_llm = False
    fallback_reason = None
    
    # Try LLM parser first if enabled
    if PARSER_ENABLED and use_llm_fallback:
        query = parse_query_with_llm(user_message, session_context)
        if query:
            used_llm = True
            logger.info(f"Used LLM parser for: {user_message[:50]}")
        else:
            fallback_reason = "llm_parse_failed"
            logger.warning(f"LLM parser failed, falling back to deterministic for: {user_message[:50]}")
    else:
        fallback_reason = "llm_disabled"
    
    # Fallback to deterministic parsing if LLM failed or disabled
    if query is None:
        query = _parse_deterministic(user_message, session_context)
        logger.info(f"Used deterministic parser for: {user_message[:50]} (reason: {fallback_reason})")
    
    # Validate the parsed query
    if not validate_parsed_query(query):
        logger.error(f"Parsed query failed validation, falling back")
        query = _parse_deterministic(user_message, session_context)
        fallback_reason = "validation_failed"
    
    # Normalize fields (Phase 3)
    query = _normalize_query(query)
    
    # Resolve company names and relative periods (Phase 4)
    query = _resolve_entities(query, session_context)
    
    # Apply session context resolution (Phase 5)
    query = _apply_session_context(query, session_context)
    
    # Apply clarification logic (Phase 6)
    query = _apply_clarification_logic(query, session_context)
    
    # Log parse attempt
    log_parse_attempt(user_message, {
        'intent': query.intent,
        'symbol': query.symbol,
        'quarter': query.quarter,
        'needs_clarification': query.needs_clarification,
        'missing_fields': query.missing_fields,
        'used_llm': used_llm,
        'fallback_reason': fallback_reason
    })
    
    return query


def _parse_deterministic(
    user_message: str,
    session_context: Dict[str, Any]
) -> ParsedQuery:
    """
    Deterministic fallback parser using regex and keyword extraction.
    
    Used when LLM parsing fails or is disabled.
    """
    symbol = _extract_symbol_deterministic(user_message)
    quarter = _extract_quarter_deterministic(user_message)
    intent = _detect_intent_deterministic(user_message)
    section = _extract_section_constraint(user_message)
    speaker = _extract_speaker_constraint(user_message)
    topic = _extract_topic(user_message)
    
    query = ParsedQuery(
        intent=intent,
        symbol=symbol,
        company_name=None,
        quarter=quarter,
        relative_period=None,
        requested_section=section,
        requested_speaker=speaker,
        topic=topic,
        comparison_mode=False,
        needs_clarification=False,
        missing_fields=[],
        clarification_message=None,
        confidence='medium',
        raw_input=user_message
    )
    
    return query


def _normalize_query(query: ParsedQuery) -> ParsedQuery:
    """
    Normalize query fields to canonical formats.
    
    Phase 3: Deterministic normalization for:
    - Symbol casing (uppercase)
    - Quarter format (YYYYQN)
    - Confidence validation
    """
    # Normalize symbol to uppercase
    if query.symbol:
        query.symbol = query.symbol.upper()
    
    # Normalize quarter format
    if query.quarter:
        # Already in YYYYQN format from parser
        query.quarter = query.quarter.upper()
    
    # Validate confidence
    if query.confidence not in VALID_CONFIDENCE:
        logger.warning(f"Invalid confidence '{query.confidence}', defaulting to 'medium'")
        query.confidence = 'medium'
    
    return query


def _resolve_entities(
    query: ParsedQuery,
    session_context: Dict[str, Any]
) -> ParsedQuery:
    """
    Resolve company names to tickers and relative periods to quarters.
    
    Phase 4: Deterministic entity resolution using:
    - Alpha Vantage SYMBOL_SEARCH for company_name -> symbol
    - Transcript availability probing for relative_period -> quarter
    """
    # Resolve company name to symbol if needed
    if query.company_name and not query.symbol:
        logger.info(f"Resolving company name '{query.company_name}' to symbol")
        resolved_symbol = resolve_company_name_to_symbol(query.company_name)
        
        if resolved_symbol:
            query.symbol = resolved_symbol
            logger.info(f"Resolved '{query.company_name}' -> {resolved_symbol}")
        else:
            # Could not resolve - mark for clarification
            query.needs_clarification = True
            if 'symbol' not in query.missing_fields:
                query.missing_fields.append('symbol')
            logger.warning(f"Could not resolve company name '{query.company_name}' to symbol")
    
    # Resolve relative period to quarter if needed
    if query.relative_period and not query.quarter and query.symbol:
        logger.info(f"Resolving relative period '{query.relative_period}' for {query.symbol}")
        
        if query.relative_period.lower() in ['latest', 'last', 'most recent', 'recent']:
            resolved_quarter = resolve_latest_quarter_for_symbol(query.symbol)
            
            if resolved_quarter:
                query.quarter = resolved_quarter
                logger.info(f"Resolved 'latest' for {query.symbol} -> {resolved_quarter}")
            else:
                # Could not resolve - mark for clarification
                query.needs_clarification = True
                if 'quarter' not in query.missing_fields:
                    query.missing_fields.append('quarter')
                logger.warning(f"Could not find latest quarter for {query.symbol}")
    
    return query


def _apply_session_context(
    query: ParsedQuery,
    session_context: Dict[str, Any]
) -> ParsedQuery:
    """
    Apply session context to fill in missing fields.
    
    Only applies context if user didn't explicitly mention new values.
    """
    from_session_context = False
    
    # Resolve symbol from session context
    if query.symbol is None and 'last_resolved_symbol' in session_context:
        # Only carry forward if user didn't mention a new company
        if not _mentions_company_name(query.raw_input):
            query.symbol = session_context['last_resolved_symbol']
            from_session_context = True
    
    # Resolve quarter from session context
    if query.quarter is None and 'last_resolved_quarter' in session_context:
        # Only carry forward if user didn't mention a new period
        if not _mentions_period(query.raw_input):
            query.quarter = session_context['last_resolved_quarter']
            from_session_context = True
    
    # Log session context usage
    if from_session_context:
        log_session_context_usage(
            had_context=True,
            symbol_from_context=query.symbol if from_session_context else None,
            quarter_from_context=query.quarter if from_session_context else None
        )
    
    return query


def _apply_clarification_logic(
    query: ParsedQuery,
    session_context: Dict[str, Any]
) -> ParsedQuery:
    """
    Apply clarification logic to determine if user needs to provide more info.
    
    Triggers clarification if:
    - Low confidence from LLM
    - Missing required fields for intent
    - Contradictions or ambiguities
    """
    needs_clarification = query.needs_clarification
    missing_fields = list(query.missing_fields) if query.missing_fields else []
    confidence = query.confidence
    
    # Check if low confidence should trigger clarification
    if query.confidence == 'low' and not needs_clarification:
        needs_clarification = True
    
    # Check completeness based on intent
    if query.intent in ['fetch', 'summarize']:
        has_transcript = session_context.get('has_active_transcript', False)
        
        if not has_transcript:
            if query.symbol is None and 'symbol' not in missing_fields:
                needs_clarification = True
                missing_fields.append('symbol')
            if query.quarter is None and 'quarter' not in missing_fields:
                needs_clarification = True
                missing_fields.append('quarter')
    
    elif query.intent == 'qa':
        has_transcript = session_context.get('has_active_transcript', False)
        
        if not has_transcript:
            if query.symbol is None and 'symbol' not in missing_fields:
                needs_clarification = True
                missing_fields.append('symbol')
            if query.quarter is None and 'quarter' not in missing_fields:
                needs_clarification = True
                missing_fields.append('quarter')
    
    # Generate clarification message if needed
    clarification_message = query.clarification_message
    if needs_clarification and not clarification_message:
        clarification_message = _generate_clarification_message(missing_fields)
        confidence = 'low'
    
    # Update query with clarification info
    query.needs_clarification = needs_clarification
    query.missing_fields = missing_fields
    query.clarification_message = clarification_message
    query.confidence = confidence
    
    return query


def _mentions_company_name(text: str) -> bool:
    """Check if text mentions a new company name."""
    # Simple heuristic: look for capitalized words that might be company names
    # More sophisticated version would use NER or company name list
    return False  # Conservative: assume no company name unless explicit ticker


def _mentions_period(text: str) -> bool:
    """Check if text mentions a time period."""
    lower = text.lower()
    period_indicators = ['quarter', 'q1', 'q2', 'q3', 'q4', '2024', '2023', '2025', 'latest', 'last', 'recent']
    return any(ind in lower for ind in period_indicators)


def _generate_clarification_message(missing_fields: list) -> str:
    """Generate user-facing clarification message."""
    if not missing_fields:
        return None
    
    field_descriptions = {
        'symbol': 'ticker symbol',
        'quarter': 'quarter (e.g., Q1 2024 or 2024Q1)',
        'company': 'company name'
    }
    
    missing_descriptions = [field_descriptions.get(f, f) for f in missing_fields]
    
    if len(missing_descriptions) == 1:
        return f"I need the {missing_descriptions[0]} to proceed. Please provide it in your message."
    else:
        return f"I need the {' and '.join(missing_descriptions)} to proceed. Please provide them in your message."


def validate_parsed_query(query: ParsedQuery) -> bool:
    """
    Validate that a parsed query has valid field values.
    
    Args:
        query: ParsedQuery instance
    
    Returns:
        True if valid, False otherwise
    """
    # Validate intent
    if query.intent not in VALID_INTENTS:
        logger.warning(f"Invalid intent: {query.intent}")
        log_parse_failure(query.raw_input, f"Invalid intent: {query.intent}")
        return False
    
    # Validate section if present
    if query.requested_section not in VALID_SECTIONS:
        logger.warning(f"Invalid section: {query.requested_section}")
        log_parse_failure(query.raw_input, f"Invalid section: {query.requested_section}")
        return False
    
    # Validate quarter format if present
    if query.quarter and not re.match(r'^\d{4}Q[1-4]$', query.quarter):
        logger.warning(f"Invalid quarter format: {query.quarter}")
        log_parse_failure(query.raw_input, f"Invalid quarter format: {query.quarter}")
        return False
    
    # Validate symbol format if present
    if query.symbol and not re.match(r'^[A-Z]{2,5}$', query.symbol):
        logger.warning(f"Invalid symbol format: {query.symbol}")
        log_parse_failure(query.raw_input, f"Invalid symbol format: {query.symbol}")
        return False
    
    return True
