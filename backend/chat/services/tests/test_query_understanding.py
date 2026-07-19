"""
Tests for query understanding service.

Phase 1: Tests for LLM parser contract and validation.
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings

from chat.services.query_understanding import (
    parse_query_with_llm,
    parse_query,
    validate_parsed_query,
    _parse_deterministic,
    _apply_session_context,
    _apply_clarification_logic
)
from chat.services.query_schema import ParsedQuery


class TestLLMParserContract(TestCase):
    """Test the LLM parser contract and JSON schema validation."""
    
    @override_settings(OPENAI_API_KEY='test-key')
    @patch('chat.services.query_understanding.OpenAI')
    def test_parse_query_with_llm_success(self, mock_openai_class):
        """Test successful LLM parsing with valid JSON response."""
        # Mock OpenAI response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'intent': 'fetch',
            'symbol': 'AAPL',
            'company_name': None,
            'quarter': '2024Q1',
            'relative_period': None,
            'requested_section': None,
            'requested_speaker': None,
            'topic': None,
            'needs_clarification': False,
            'missing_fields': [],
            'confidence': 'high'
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test
        query = parse_query_with_llm("fetch AAPL Q1 2024", {})
        
        # Assertions
        self.assertIsNotNone(query)
        self.assertEqual(query.intent, 'fetch')
        self.assertEqual(query.symbol, 'AAPL')
        self.assertEqual(query.quarter, '2024Q1')
        self.assertEqual(query.confidence, 'high')
        self.assertFalse(query.needs_clarification)
    
    @override_settings(OPENAI_API_KEY='test-key')
    @patch('chat.services.query_understanding.OpenAI')
    def test_parse_query_with_llm_invalid_json(self, mock_openai_class):
        """Test LLM parser with invalid JSON response."""
        # Mock OpenAI response with invalid JSON
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "This is not JSON"
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test
        query = parse_query_with_llm("fetch AAPL Q1 2024", {})
        
        # Assertions
        self.assertIsNone(query)  # Should return None on failure
    
    @override_settings(OPENAI_API_KEY='test-key')
    @patch('chat.services.query_understanding.OpenAI')
    def test_parse_query_with_llm_exception(self, mock_openai_class):
        """Test LLM parser with API exception."""
        # Mock OpenAI exception
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error")
        
        # Test
        query = parse_query_with_llm("fetch AAPL Q1 2024", {})
        
        # Assertions
        self.assertIsNone(query)  # Should return None on exception
    
    @override_settings(OPENAI_API_KEY='test-key')
    @patch('chat.services.query_understanding.OpenAI')
    def test_llm_parser_handles_unknown_intent_gracefully(self, mock_openai_class):
        """Test LLM parser handles unknown intent by returning parseable result."""
        # Mock OpenAI response with unknown intent
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'intent': 'unknown_intent',
            'symbol': 'AAPL',
            'company_name': None,
            'quarter': '2024Q1',
            'relative_period': None,
            'requested_section': None,
            'requested_speaker': None,
            'topic': None,
            'needs_clarification': False,
            'missing_fields': [],
            'confidence': 'high'
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test - parser should return the query, validation will catch the bad intent
        query = parse_query_with_llm("do something weird with AAPL Q1 2024", {})
        
        # Assertions
        self.assertIsNotNone(query)
        self.assertEqual(query.intent, 'unknown_intent')
        # Validation layer should reject this
        self.assertFalse(validate_parsed_query(query))
    
    @override_settings(OPENAI_API_KEY='test-key')
    @patch('chat.services.query_understanding.OpenAI')
    def test_llm_parser_handles_invalid_section_gracefully(self, mock_openai_class):
        """Test LLM parser handles invalid section by returning parseable result."""
        # Mock OpenAI response with invalid section
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'intent': 'qa',
            'symbol': 'AAPL',
            'company_name': None,
            'quarter': '2024Q1',
            'relative_period': None,
            'requested_section': 'invalid_section',
            'requested_speaker': None,
            'topic': None,
            'needs_clarification': False,
            'missing_fields': [],
            'confidence': 'high'
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test - parser should return the query, validation will catch the bad section
        query = parse_query_with_llm("what was said in the weird section?", {})
        
        # Assertions
        self.assertIsNotNone(query)
        self.assertEqual(query.requested_section, 'invalid_section')
        # Validation layer should reject this
        self.assertFalse(validate_parsed_query(query))
    
    @override_settings(OPENAI_API_KEY='test-key')
    @patch('chat.services.query_understanding.OpenAI')
    def test_llm_parser_defaults_missing_confidence(self, mock_openai_class):
        """Test LLM parser defaults to 'medium' when confidence is missing."""
        # Mock OpenAI response without confidence field
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'intent': 'fetch',
            'symbol': 'AAPL',
            'company_name': None,
            'quarter': '2024Q1',
            'relative_period': None,
            'requested_section': None,
            'requested_speaker': None,
            'topic': None,
            'needs_clarification': False,
            'missing_fields': []
            # Note: confidence field is missing
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test
        query = parse_query_with_llm("fetch AAPL Q1 2024", {})
        
        # Assertions
        self.assertIsNotNone(query)
        self.assertEqual(query.confidence, 'medium')  # Should default to medium


class TestQueryValidation(TestCase):
    """Test query validation logic."""
    
    def test_validate_valid_query(self):
        """Test validation of a valid query."""
        query = ParsedQuery(
            intent='fetch',
            symbol='AAPL',
            company_name=None,
            quarter='2024Q1',
            relative_period=None,
            requested_section=None,
            requested_speaker=None,
            topic=None,
            comparison_mode=False,
            needs_clarification=False,
            missing_fields=[],
            clarification_message=None,
            confidence='high',
            raw_input='fetch AAPL Q1 2024'
        )
        
        self.assertTrue(validate_parsed_query(query))
    
    def test_validate_invalid_intent(self):
        """Test validation rejects invalid intent."""
        query = ParsedQuery(
            intent='invalid_intent',
            symbol='AAPL',
            company_name=None,
            quarter='2024Q1',
            relative_period=None,
            requested_section=None,
            requested_speaker=None,
            topic=None,
            comparison_mode=False,
            needs_clarification=False,
            missing_fields=[],
            clarification_message=None,
            confidence='high',
            raw_input='test'
        )
        
        self.assertFalse(validate_parsed_query(query))
    
    def test_validate_invalid_section(self):
        """Test validation rejects invalid section."""
        query = ParsedQuery(
            intent='fetch',
            symbol='AAPL',
            company_name=None,
            quarter='2024Q1',
            relative_period=None,
            requested_section='invalid_section',
            requested_speaker=None,
            topic=None,
            comparison_mode=False,
            needs_clarification=False,
            missing_fields=[],
            clarification_message=None,
            confidence='high',
            raw_input='test'
        )
        
        self.assertFalse(validate_parsed_query(query))
    
    def test_validate_invalid_quarter_format(self):
        """Test validation rejects invalid quarter format."""
        query = ParsedQuery(
            intent='fetch',
            symbol='AAPL',
            company_name=None,
            quarter='Q1-2024',  # Invalid format
            relative_period=None,
            requested_section=None,
            requested_speaker=None,
            topic=None,
            comparison_mode=False,
            needs_clarification=False,
            missing_fields=[],
            clarification_message=None,
            confidence='high',
            raw_input='test'
        )
        
        self.assertFalse(validate_parsed_query(query))
    
    def test_validate_invalid_symbol_format(self):
        """Test validation rejects invalid symbol format."""
        query = ParsedQuery(
            intent='fetch',
            symbol='A',  # Too short
            company_name=None,
            quarter='2024Q1',
            relative_period=None,
            requested_section=None,
            requested_speaker=None,
            topic=None,
            comparison_mode=False,
            needs_clarification=False,
            missing_fields=[],
            clarification_message=None,
            confidence='high',
            raw_input='test'
        )
        
        self.assertFalse(validate_parsed_query(query))
    
    def test_validate_invalid_confidence(self):
        """Test validation handles invalid confidence by normalizing it."""
        query = ParsedQuery(
            intent='fetch',
            symbol='AAPL',
            company_name=None,
            quarter='2024Q1',
            relative_period=None,
            requested_section=None,
            requested_speaker=None,
            topic=None,
            comparison_mode=False,
            needs_clarification=False,
            missing_fields=[],
            clarification_message=None,
            confidence='invalid',  # Invalid confidence value
            raw_input='test'
        )
        
        # Normalization should happen before validation
        # But we still want to ensure the query is otherwise valid
        self.assertTrue(validate_parsed_query(query))


class TestParseQueryIntegration(TestCase):
    """Test the main parse_query function with LLM primary and deterministic fallback."""
    
    @override_settings(OPENAI_API_KEY='test-key', QUERY_PARSER_ENABLED=True)
    @patch('chat.services.query_understanding.OpenAI')
    def test_parse_query_uses_llm_first(self, mock_openai_class):
        """Test that parse_query uses LLM as primary path."""
        # Mock successful LLM response
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            'intent': 'qa',
            'symbol': None,
            'company_name': 'Apple',
            'quarter': None,
            'relative_period': 'latest',
            'requested_section': None,
            'requested_speaker': None,
            'topic': 'guidance',
            'needs_clarification': False,
            'missing_fields': [],
            'confidence': 'high'
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        # Test
        query = parse_query("what's the guidance for Apple's latest quarter?", {})
        
        # Assertions
        self.assertEqual(query.intent, 'qa')
        self.assertEqual(query.company_name, 'Apple')
        self.assertEqual(query.relative_period, 'latest')
        self.assertEqual(query.topic, 'guidance')
    
    @override_settings(QUERY_PARSER_ENABLED=False)
    def test_parse_query_uses_deterministic_when_disabled(self):
        """Test that parse_query uses deterministic parser when LLM is disabled."""
        query = parse_query("fetch AAPL 2024Q1", {})
        
        # Assertions
        self.assertEqual(query.intent, 'fetch')
        self.assertEqual(query.symbol, 'AAPL')
        self.assertEqual(query.quarter, '2024Q1')
    
    @override_settings(OPENAI_API_KEY='test-key', QUERY_PARSER_ENABLED=True)
    @patch('chat.services.query_understanding.OpenAI')
    def test_parse_query_falls_back_on_llm_failure(self, mock_openai_class):
        """Test that parse_query falls back to deterministic on LLM failure."""
        # Mock LLM failure
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API error")
        
        # Test
        query = parse_query("fetch AAPL 2024Q1", {})
        
        # Assertions - should still get a result from deterministic parser
        self.assertEqual(query.intent, 'fetch')
        self.assertEqual(query.symbol, 'AAPL')
        self.assertEqual(query.quarter, '2024Q1')


class TestSessionContextApplication(TestCase):
    """Test session context resolution logic."""
    
    def test_apply_session_context_fills_missing_symbol(self):
        """Test that session context fills missing symbol."""
        query = ParsedQuery(
            intent='qa',
            symbol=None,
            company_name=None,
            quarter='2024Q1',
            relative_period=None,
            requested_section=None,
            requested_speaker=None,
            topic='guidance',
            comparison_mode=False,
            needs_clarification=False,
            missing_fields=[],
            clarification_message=None,
            confidence='high',
            raw_input="what's the guidance?"
        )
        
        session_context = {
            'last_resolved_symbol': 'AAPL',
            'last_resolved_quarter': '2024Q1'
        }
        
        resolved_query = _apply_session_context(query, session_context)
        
        self.assertEqual(resolved_query.symbol, 'AAPL')
    
    def test_apply_session_context_respects_explicit_mentions(self):
        """Test that explicit mentions override session context."""
        query = ParsedQuery(
            intent='qa',
            symbol='MSFT',
            company_name=None,
            quarter='2024Q1',
            relative_period=None,
            requested_section=None,
            requested_speaker=None,
            topic='guidance',
            comparison_mode=False,
            needs_clarification=False,
            missing_fields=[],
            clarification_message=None,
            confidence='high',
            raw_input="what's Microsoft's guidance?"
        )
        
        session_context = {
            'last_resolved_symbol': 'AAPL'
        }
        
        resolved_query = _apply_session_context(query, session_context)
        
        self.assertEqual(resolved_query.symbol, 'MSFT')  # Should keep explicit mention


class TestClarificationLogic(TestCase):
    """Test clarification logic."""
    
    def test_clarification_triggered_for_missing_required_fields(self):
        """Test that clarification is triggered when required fields are missing."""
        query = ParsedQuery(
            intent='fetch',
            symbol=None,
            company_name=None,
            quarter=None,
            relative_period=None,
            requested_section=None,
            requested_speaker=None,
            topic=None,
            comparison_mode=False,
            needs_clarification=False,
            missing_fields=[],
            clarification_message=None,
            confidence='high',
            raw_input="fetch the transcript"
        )
        
        session_context = {'has_active_transcript': False}
        
        clarified_query = _apply_clarification_logic(query, session_context)
        
        self.assertTrue(clarified_query.needs_clarification)
        self.assertIn('symbol', clarified_query.missing_fields)
        self.assertIn('quarter', clarified_query.missing_fields)
        self.assertIsNotNone(clarified_query.clarification_message)
    
    def test_clarification_triggered_for_low_confidence(self):
        """Test that clarification is triggered for low confidence."""
        query = ParsedQuery(
            intent='qa',
            symbol='AAPL',
            company_name=None,
            quarter='2024Q1',
            relative_period=None,
            requested_section=None,
            requested_speaker=None,
            topic=None,
            comparison_mode=False,
            needs_clarification=False,
            missing_fields=[],
            clarification_message=None,
            confidence='low',
            raw_input="tell me something about it"
        )
        
        session_context = {'has_active_transcript': True}
        
        clarified_query = _apply_clarification_logic(query, session_context)
        
        self.assertTrue(clarified_query.needs_clarification)
