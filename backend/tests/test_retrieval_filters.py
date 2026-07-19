"""
Tests for retrieval filters (Phase 4).

Tests metadata-based filtering for section and speaker constraints.
"""

import pytest
from unittest.mock import Mock, patch
from transcripts.services.chunking import retrieve_top_k
from transcripts.models import TranscriptChunk


class TestRetrievalFilters:
    """Test retrieval with metadata filters."""
    
    def test_section_filter_qa_only(self):
        """Test filtering to Q&A section only."""
        # Create mock transcript
        transcript = Mock()
        transcript.id = 'test-id'
        
        # Create mock chunks with different sections
        prepared_chunk = Mock(spec=TranscriptChunk)
        prepared_chunk.section = 'prepared'
        prepared_chunk.text = 'prepared remarks about revenue'
        prepared_chunk.token_count = 100
        prepared_chunk.speaker = 'CEO'
        
        qa_chunk = Mock(spec=TranscriptChunk)
        qa_chunk.section = 'qa'
        qa_chunk.text = 'analyst question about revenue'
        qa_chunk.token_count = 100
        qa_chunk.speaker = 'Analyst'
        
        with patch('transcripts.services.chunking.get_or_create_chunks') as mock_get_chunks:
            mock_get_chunks.return_value = [prepared_chunk, qa_chunk]
            
            # Filter to Q&A only
            results = retrieve_top_k(
                transcript, 
                'revenue', 
                k=10,
                section_filter='qa'
            )
            
            # Should only return QA chunk
            assert len(results) == 1
            assert results[0].section == 'qa'
    
    def test_section_filter_prepared_only(self):
        """Test filtering to prepared remarks only."""
        transcript = Mock()
        
        prepared_chunk = Mock(spec=TranscriptChunk)
        prepared_chunk.section = 'prepared'
        prepared_chunk.text = 'prepared remarks about guidance'
        prepared_chunk.token_count = 100
        prepared_chunk.speaker = 'CFO'
        
        qa_chunk = Mock(spec=TranscriptChunk)
        qa_chunk.section = 'qa'
        qa_chunk.text = 'analyst question about guidance'
        qa_chunk.token_count = 100
        qa_chunk.speaker = 'Analyst'
        
        with patch('transcripts.services.chunking.get_or_create_chunks') as mock_get_chunks:
            mock_get_chunks.return_value = [prepared_chunk, qa_chunk]
            
            results = retrieve_top_k(
                transcript, 
                'guidance', 
                k=10,
                section_filter='prepared'
            )
            
            assert len(results) == 1
            assert results[0].section == 'prepared'
    
    def test_speaker_filter_cfo(self):
        """Test filtering by speaker."""
        transcript = Mock()
        
        cfo_chunk = Mock(spec=TranscriptChunk)
        cfo_chunk.section = 'prepared'
        cfo_chunk.text = 'CFO discussing margins'
        cfo_chunk.token_count = 100
        cfo_chunk.speaker = 'John Smith, CFO'
        
        ceo_chunk = Mock(spec=TranscriptChunk)
        ceo_chunk.section = 'prepared'
        ceo_chunk.text = 'CEO discussing margins'
        ceo_chunk.token_count = 100
        ceo_chunk.speaker = 'Jane Doe, CEO'
        
        with patch('transcripts.services.chunking.get_or_create_chunks') as mock_get_chunks:
            mock_get_chunks.return_value = [cfo_chunk, ceo_chunk]
            
            results = retrieve_top_k(
                transcript, 
                'margins', 
                k=10,
                speaker_filter='CFO'
            )
            
            assert len(results) == 1
            assert 'CFO' in results[0].speaker
    
    def test_combined_filters(self):
        """Test combining section and speaker filters."""
        transcript = Mock()
        
        # CFO in prepared remarks
        chunk1 = Mock(spec=TranscriptChunk)
        chunk1.section = 'prepared'
        chunk1.text = 'CFO prepared remarks about AI'
        chunk1.token_count = 100
        chunk1.speaker = 'CFO'
        
        # CFO in Q&A
        chunk2 = Mock(spec=TranscriptChunk)
        chunk2.section = 'qa'
        chunk2.text = 'CFO answering AI question'
        chunk2.token_count = 100
        chunk2.speaker = 'CFO'
        
        # CEO in Q&A
        chunk3 = Mock(spec=TranscriptChunk)
        chunk3.section = 'qa'
        chunk3.text = 'CEO answering AI question'
        chunk3.token_count = 100
        chunk3.speaker = 'CEO'
        
        with patch('transcripts.services.chunking.get_or_create_chunks') as mock_get_chunks:
            mock_get_chunks.return_value = [chunk1, chunk2, chunk3]
            
            # Filter for CFO in Q&A only
            results = retrieve_top_k(
                transcript, 
                'AI', 
                k=10,
                section_filter='qa',
                speaker_filter='CFO'
            )
            
            assert len(results) == 1
            assert results[0].section == 'qa'
            assert 'CFO' in results[0].speaker
    
    def test_no_matches_after_filtering(self):
        """Test empty results when filters match nothing."""
        transcript = Mock()
        
        chunk = Mock(spec=TranscriptChunk)
        chunk.section = 'prepared'
        chunk.text = 'CEO prepared remarks'
        chunk.token_count = 100
        chunk.speaker = 'CEO'
        
        with patch('transcripts.services.chunking.get_or_create_chunks') as mock_get_chunks:
            mock_get_chunks.return_value = [chunk]
            
            # Filter for Q&A when only prepared exists
            results = retrieve_top_k(
                transcript, 
                'remarks', 
                k=10,
                section_filter='qa'
            )
            
            assert len(results) == 0
