"""
Tests for Alpha Vantage entity resolution functions.

Phase 4: Tests for company name to symbol resolution and quarter resolution.
"""
import json
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings

from transcripts.services.fetch_alpha_vantage import (
    resolve_company_name_to_symbol,
    resolve_latest_quarter_for_symbol,
    _generate_candidate_quarters
)


class TestCompanyNameResolution(TestCase):
    """Test company name to symbol resolution using SYMBOL_SEARCH."""
    
    @override_settings(ALPHAVANTAGE_API_KEY='test-key')
    @patch('transcripts.services.fetch_alpha_vantage.httpx.get')
    def test_resolve_company_name_success(self, mock_get):
        """Test successful company name resolution with high confidence match."""
        # Mock Alpha Vantage SYMBOL_SEARCH response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bestMatches": [
                {
                    "1. symbol": "AAPL",
                    "2. name": "Apple Inc.",
                    "3. type": "Equity",
                    "4. region": "United States",
                    "5. marketOpen": "09:30",
                    "6. marketClose": "16:00",
                    "7. timezone": "UTC-04",
                    "8. currency": "USD",
                    "9. matchScore": "0.8889"
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Test
        result = resolve_company_name_to_symbol("Apple")
        
        # Assertions
        self.assertEqual(result, "AAPL")
        mock_get.assert_called_once()
        call_args = mock_get.call_args
        self.assertEqual(call_args[1]['params']['function'], 'SYMBOL_SEARCH')
        self.assertEqual(call_args[1]['params']['keywords'], 'Apple')
    
    @override_settings(ALPHAVANTAGE_API_KEY='test-key')
    @patch('transcripts.services.fetch_alpha_vantage.httpx.get')
    def test_resolve_company_name_low_confidence_rejects(self, mock_get):
        """Test that low confidence matches are rejected."""
        # Mock Alpha Vantage response with low match score
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bestMatches": [
                {
                    "1. symbol": "AAPL",
                    "2. name": "Apple Inc.",
                    "3. type": "Equity",
                    "9. matchScore": "0.5"  # Below threshold
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Test
        result = resolve_company_name_to_symbol("Aple")
        
        # Assertions
        self.assertIsNone(result)
    
    @override_settings(ALPHAVANTAGE_API_KEY='test-key')
    @patch('transcripts.services.fetch_alpha_vantage.httpx.get')
    def test_resolve_company_name_non_equity_rejects(self, mock_get):
        """Test that non-Equity type matches are rejected."""
        # Mock Alpha Vantage response with non-Equity type
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bestMatches": [
                {
                    "1. symbol": "SPY",
                    "2. name": "SPDR S&P 500 ETF Trust",
                    "3. type": "ETF",  # Not Equity
                    "9. matchScore": "0.9"
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Test
        result = resolve_company_name_to_symbol("SPY")
        
        # Assertions
        self.assertIsNone(result)
    
    @override_settings(ALPHAVANTAGE_API_KEY='test-key')
    @patch('transcripts.services.fetch_alpha_vantage.httpx.get')
    def test_resolve_company_name_no_matches(self, mock_get):
        """Test handling when no matches are found."""
        # Mock Alpha Vantage response with no matches
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bestMatches": []
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Test
        result = resolve_company_name_to_symbol("NonexistentCompany")
        
        # Assertions
        self.assertIsNone(result)
    
    @override_settings(ALPHAVANTAGE_API_KEY='test-key')
    @patch('transcripts.services.fetch_alpha_vantage.httpx.get')
    def test_resolve_company_name_rate_limit(self, mock_get):
        """Test handling of rate limit errors."""
        # Mock Alpha Vantage rate limit response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Note": "Thank you for using Alpha Vantage! Our standard API rate limit is..."
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Test
        result = resolve_company_name_to_symbol("Apple")
        
        # Assertions
        self.assertIsNone(result)
    
    @override_settings(ALPHAVANTAGE_API_KEY='test-key')
    @patch('transcripts.services.fetch_alpha_vantage.httpx.get')
    def test_resolve_company_name_api_error(self, mock_get):
        """Test handling of API errors."""
        # Mock Alpha Vantage error response
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "Error Message": "Invalid API call"
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Test
        result = resolve_company_name_to_symbol("Apple")
        
        # Assertions
        self.assertIsNone(result)
    
    def test_resolve_company_name_empty_input(self):
        """Test handling of empty company name."""
        result = resolve_company_name_to_symbol("")
        
        self.assertIsNone(result)
    
    def test_resolve_company_name_none_input(self):
        """Test handling of None company name."""
        result = resolve_company_name_to_symbol(None)
        
        self.assertIsNone(result)


class TestQuarterResolution(TestCase):
    """Test latest quarter resolution via transcript availability probing."""
    
    def test_generate_candidate_quarters(self):
        """Test generation of candidate quarters from current date."""
        # Test with count=3 (default)
        candidates = _generate_candidate_quarters(3)
        
        # Assertions
        self.assertEqual(len(candidates), 3)
        # Each should match YYYYQN format
        for quarter in candidates:
            self.assertRegex(quarter, r'^\d{4}Q[1-4]$')
        # Should be in descending order (newest first)
        # We can't hardcode expected values since current date varies
    
    @patch('transcripts.services.fetch_alpha_vantage.Transcript.objects.get')
    def test_resolve_latest_quarter_from_cache(self, mock_transcript_get):
        """Test that latest quarter is resolved from cached transcript."""
        # Mock cached transcript in database
        mock_transcript = MagicMock()
        mock_transcript_get.return_value = mock_transcript
        
        # Test
        result = resolve_latest_quarter_for_symbol("AAPL")
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertRegex(result, r'^\d{4}Q[1-4]$')
        mock_transcript_get.assert_called()
    
    @patch('transcripts.services.fetch_alpha_vantage.AlphaVantageRestClient')
    @patch('transcripts.services.fetch_alpha_vantage.Transcript.objects.get')
    def test_resolve_latest_quarter_probes_api(self, mock_transcript_get, mock_client_class):
        """Test that latest quarter probes Alpha Vantage API when not cached."""
        from transcripts.services.fetch_alpha_vantage import TranscriptNotAvailable
        from transcripts.models import Transcript
        
        # Mock no cached transcripts - use DoesNotExist
        mock_transcript_get.side_effect = Transcript.DoesNotExist()
        
        # Mock Alpha Vantage client
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # First 2 quarters don't exist, 3rd one does
        def fetch_side_effect(symbol, quarter):
            if quarter.endswith('Q3') or quarter.endswith('Q2'):
                raise TranscriptNotAvailable(f"No transcript for {quarter}")
            return {"symbol": symbol, "quarter": quarter, "transcript": [{"content": "test"}]}
        
        mock_client.fetch_transcript.side_effect = fetch_side_effect
        
        # Test
        result = resolve_latest_quarter_for_symbol("AAPL", max_quarters_back=3)
        
        # Assertions
        self.assertIsNotNone(result)
        self.assertRegex(result, r'^\d{4}Q[1-4]$')
        # Should have tried multiple quarters
        self.assertGreaterEqual(mock_client.fetch_transcript.call_count, 1)
    
    @patch('transcripts.services.fetch_alpha_vantage.AlphaVantageRestClient')
    @patch('transcripts.services.fetch_alpha_vantage.Transcript.objects.get')
    def test_resolve_latest_quarter_no_transcripts_found(self, mock_transcript_get, mock_client_class):
        """Test that None is returned when no recent transcripts exist."""
        from transcripts.services.fetch_alpha_vantage import TranscriptNotAvailable
        from transcripts.models import Transcript
        
        # Mock no cached transcripts - use DoesNotExist
        mock_transcript_get.side_effect = Transcript.DoesNotExist()
        
        # Mock Alpha Vantage client - all probes fail
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.fetch_transcript.side_effect = TranscriptNotAvailable("No transcript")
        
        # Test
        result = resolve_latest_quarter_for_symbol("AAPL", max_quarters_back=3)
        
        # Assertions
        self.assertIsNone(result)
        # Should have tried all 3 quarters
        self.assertEqual(mock_client.fetch_transcript.call_count, 3)
    
    def test_resolve_latest_quarter_none_symbol(self):
        """Test handling of None symbol."""
        result = resolve_latest_quarter_for_symbol(None)
        
        self.assertIsNone(result)
    
    def test_resolve_latest_quarter_empty_symbol(self):
        """Test handling of empty symbol."""
        result = resolve_latest_quarter_for_symbol("")
        
        self.assertIsNone(result)


class TestEntityResolutionIntegration(TestCase):
    """Test entity resolution integration in query understanding pipeline."""
    
    @override_settings(ALPHAVANTAGE_API_KEY='test-key')
    @patch('transcripts.services.fetch_alpha_vantage.httpx.get')
    def test_resolve_entities_company_name_to_symbol(self, mock_get):
        """Test that _resolve_entities calls company name resolution."""
        from chat.services.query_understanding import _resolve_entities
        from chat.services.query_schema import ParsedQuery
        
        # Mock successful SYMBOL_SEARCH
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "bestMatches": [{
                "1. symbol": "AAPL",
                "3. type": "Equity",
                "9. matchScore": "0.9"
            }]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Create query with company name
        query = ParsedQuery(
            intent='fetch',
            symbol=None,
            company_name='Apple',
            quarter='2024Q1',
            raw_input='fetch Apple Q1 2024'
        )
        
        # Test
        resolved_query = _resolve_entities(query, {})
        
        # Assertions
        self.assertEqual(resolved_query.symbol, 'AAPL')
    
    @override_settings(ALPHAVANTAGE_API_KEY='test-key')
    @patch('transcripts.services.fetch_alpha_vantage.httpx.get')
    def test_resolve_entities_marks_clarification_on_failure(self, mock_get):
        """Test that failed resolution triggers clarification."""
        from chat.services.query_understanding import _resolve_entities
        from chat.services.query_schema import ParsedQuery
        
        # Mock no matches
        mock_response = MagicMock()
        mock_response.json.return_value = {"bestMatches": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response
        
        # Create query with unresolvable company name
        query = ParsedQuery(
            intent='fetch',
            symbol=None,
            company_name='UnknownCompany',
            quarter='2024Q1',
            raw_input='fetch UnknownCompany Q1 2024'
        )
        
        # Test
        resolved_query = _resolve_entities(query, {})
        
        # Assertions
        self.assertIsNone(resolved_query.symbol)
        self.assertTrue(resolved_query.needs_clarification)
        self.assertIn('symbol', resolved_query.missing_fields)
