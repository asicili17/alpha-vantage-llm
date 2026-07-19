"""
Tests for query understanding service.

Tests the hybrid parsing approach and query normalization.
"""

import pytest
from chat.services.query_understanding import (
    parse_query,
    validate_parsed_query,
    _extract_symbol_deterministic,
    _extract_quarter_deterministic,
    _detect_intent_deterministic,
    _extract_section_constraint,
    _extract_speaker_constraint
)
from chat.services.query_schema import ParsedQuery


class TestDeterministicExtraction:
    """Test deterministic extraction functions."""
    
    def test_extract_symbol(self):
        """Test symbol extraction from various formats."""
        assert _extract_symbol_deterministic("AAPL Q1 2024") == "AAPL"
        assert _extract_symbol_deterministic("fetch MSFT") == "MSFT"
        assert _extract_symbol_deterministic("what about NVDA?") == "NVDA"
        assert _extract_symbol_deterministic("no ticker here") is None
    
    def test_extract_quarter(self):
        """Test quarter extraction and normalization."""
        assert _extract_quarter_deterministic("Q1 2024") == "2024Q1"
        assert _extract_quarter_deterministic("2024 Q2") == "2024Q2"
        assert _extract_quarter_deterministic("2024Q3") == "2024Q3"
        assert _extract_quarter_deterministic("Q4-2023") == "2023Q4"
        assert _extract_quarter_deterministic("no quarter") is None
    
    def test_detect_intent_fetch(self):
        """Test fetch intent detection."""
        assert _detect_intent_deterministic("fetch AAPL Q1 2024") == "fetch"
        assert _detect_intent_deterministic("get transcript for MSFT") == "fetch"
        assert _detect_intent_deterministic("load the earnings call") == "fetch"
    
    def test_detect_intent_summarize(self):
        """Test summarize intent detection."""
        assert _detect_intent_deterministic("summarize AAPL Q1 2024") == "summarize"
        assert _detect_intent_deterministic("give me a summary") == "summarize"
        assert _detect_intent_deterministic("overview of the call") == "summarize"
    
    def test_detect_intent_qa_default(self):
        """Test that questions default to QA intent."""
        assert _detect_intent_deterministic("what did they say about AI?") == "qa"
        assert _detect_intent_deterministic("how was revenue growth?") == "qa"
    
    def test_extract_section_constraint(self):
        """Test section filter extraction."""
        assert _extract_section_constraint("Q&A only") == "qa"
        assert _extract_section_constraint("question and answer session") == "qa"
        assert _extract_section_constraint("prepared remarks only") == "prepared"
        assert _extract_section_constraint("no section mentioned") is None
    
    def test_extract_speaker_constraint(self):
        """Test speaker filter extraction."""
        assert _extract_speaker_constraint("what did the CFO say?") == "CFO"
        assert _extract_speaker_constraint("CEO mentioned") == "CEO"
        assert _extract_speaker_constraint("analyst questions") == "Analyst"
        assert _extract_speaker_constraint("no speaker mentioned") is None


class TestQueryParsing:
    """Test full query parsing."""
    
    def test_parse_explicit_fetch_request(self):
        """Test parsing explicit fetch with symbol and quarter."""
        query = parse_query("fetch AAPL Q1 2024")
        
        assert query.intent == "fetch"
        assert query.symbol == "AAPL"
        assert query.quarter == "2024Q1"
        assert not query.needs_clarification
    
    def test_parse_summarize_with_filters(self):
        """Test parsing summarize with section filter."""
        query = parse_query("summarize MSFT 2024Q2 Q&A only")
        
        assert query.intent == "summarize"
        assert query.symbol == "MSFT"
        assert query.quarter == "2024Q2"
        assert query.requested_section == "qa"
    
    def test_parse_qa_with_speaker_filter(self):
        """Test parsing Q&A with speaker constraint."""
        query = parse_query("what did the CFO say about margins?")
        
        assert query.intent == "qa"
        assert query.requested_speaker == "CFO"
        assert query.topic == "margins"
    
    def test_parse_missing_symbol_triggers_clarification(self):
        """Test that missing symbol triggers clarification."""
        query = parse_query("fetch Q1 2024", session_context={'has_active_transcript': False})
        
        assert query.needs_clarification
        assert 'symbol' in query.missing_fields
    
    def test_parse_missing_quarter_triggers_clarification(self):
        """Test that missing quarter triggers clarification."""
        query = parse_query("fetch AAPL", session_context={'has_active_transcript': False})
        
        assert query.needs_clarification
        assert 'quarter' in query.missing_fields
    
    def test_parse_uses_session_context(self):
        """Test that session context fills in missing values."""
        session_context = {
            'has_active_transcript': True,
            'last_resolved_symbol': 'AAPL',
            'last_resolved_quarter': '2024Q1'
        }
        
        query = parse_query("what about guidance?", session_context=session_context)
        
        assert query.symbol == "AAPL"
        assert query.quarter == "2024Q1"
        assert query.topic == "guidance"
    
    def test_parse_qa_without_transcript_needs_clarification(self):
        """Test Q&A without active transcript needs clarification."""
        query = parse_query(
            "what did they say about AI?",
            session_context={'has_active_transcript': False}
        )
        
        assert query.intent == "qa"
        assert query.needs_clarification


class TestQueryValidation:
    """Test query validation."""
    
    def test_validate_valid_query(self):
        """Test validation of valid query."""
        query = ParsedQuery(
            intent='fetch',
            symbol='AAPL',
            quarter='2024Q1',
            raw_input='fetch AAPL Q1 2024'
        )
        
        assert validate_parsed_query(query)
    
    def test_validate_invalid_intent(self):
        """Test validation rejects invalid intent."""
        query = ParsedQuery(
            intent='invalid',
            raw_input='test'
        )
        
        assert not validate_parsed_query(query)
    
    def test_validate_invalid_quarter_format(self):
        """Test validation rejects bad quarter format."""
        query = ParsedQuery(
            intent='fetch',
            symbol='AAPL',
            quarter='Q1-2024',  # Wrong format
            raw_input='test'
        )
        
        assert not validate_parsed_query(query)
    
    def test_validate_invalid_symbol_format(self):
        """Test validation rejects bad symbol format."""
        query = ParsedQuery(
            intent='fetch',
            symbol='apple',  # Should be uppercase
            quarter='2024Q1',
            raw_input='test'
        )
        
        assert not validate_parsed_query(query)
