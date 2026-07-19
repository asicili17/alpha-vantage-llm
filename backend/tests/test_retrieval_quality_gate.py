"""
Tests for retrieval quality gates (Phase 5).

Tests answer gating based on retrieval quality.
"""

import pytest
from unittest.mock import Mock, patch
from agent.services.qa import answer_question


class TestRetrievalQualityGate:
    """Test retrieval quality gating behavior."""
    
    def test_insufficient_chunks_triggers_low_confidence(self):
        """Test that too few chunks returns low confidence response."""
        transcript = Mock()
        
        # Mock retrieval returning only 1 chunk (below threshold of 2)
        with patch('agent.services.qa.retrieve_top_k') as mock_retrieve:
            chunk = Mock()
            chunk.id = 'chunk-1'
            chunk.text = 'some text'
            chunk.token_count = 100
            chunk.section = 'prepared'
            
            mock_retrieve.return_value = [chunk]
            
            result = answer_question(
                transcript, 
                "what about AI?",
                min_chunks_threshold=2
            )
            
            assert result['retrieval_quality'] == 'insufficient'
            assert result['confidence'] == 'low'
            assert 'not have enough' in result['answer'].lower()
    
    def test_no_chunks_triggers_insufficient(self):
        """Test that zero chunks returns insufficient quality."""
        transcript = Mock()
        
        with patch('agent.services.qa.retrieve_top_k') as mock_retrieve:
            mock_retrieve.return_value = []
            
            result = answer_question(transcript, "what about margins?")
            
            assert result['retrieval_quality'] == 'insufficient'
            assert result['chunks_used'] == 0
            assert result['confidence'] == 'low'
    
    def test_sufficient_chunks_allows_answer(self):
        """Test that sufficient chunks proceed to answer generation."""
        transcript = Mock()
        
        # Mock retrieval returning enough chunks
        with patch('agent.services.qa.retrieve_top_k') as mock_retrieve:
            with patch('agent.services.qa.OpenAI') as mock_openai:
                # Create mock chunks
                chunks = []
                for i in range(3):
                    chunk = Mock()
                    chunk.id = f'chunk-{i}'
                    chunk.text = f'text about revenue {i}'
                    chunk.token_count = 100
                    chunk.section = 'prepared'
                    chunks.append(chunk)
                
                mock_retrieve.return_value = chunks
                
                # Mock OpenAI response
                mock_client = Mock()
                mock_response = Mock()
                mock_response.choices = [Mock()]
                mock_response.choices[0].message.content = '{"answer": "Revenue grew 15%", "citations": [], "confidence": "high"}'
                mock_client.chat.completions.create.return_value = mock_response
                mock_openai.return_value = mock_client
                
                result = answer_question(
                    transcript, 
                    "what about revenue?",
                    min_chunks_threshold=2
                )
                
                # Should proceed to answer
                assert result['retrieval_quality'] == 'sufficient'
                assert result['chunks_used'] == 3
                assert 'Revenue grew' in result['answer']
    
    def test_filtered_retrieval_with_no_matches(self):
        """Test that filters returning no chunks triggers gate."""
        transcript = Mock()
        
        with patch('agent.services.qa.retrieve_top_k') as mock_retrieve:
            # Filters result in no matches
            mock_retrieve.return_value = []
            
            result = answer_question(
                transcript, 
                "what did the CFO say?",
                section_filter='qa',
                speaker_filter='CFO'
            )
            
            assert result['retrieval_quality'] == 'insufficient'
            assert 'not have enough' in result['answer'].lower()
