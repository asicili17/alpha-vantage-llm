"""
Transcript chunking service.

Handles:
- Splitting transcripts into chunks for LLM processing
- Adding metadata per chunk (speaker, section, sentiment)
- Token counting and overlap management
"""

from typing import List, Dict


class TranscriptChunker:
    """Chunks transcripts for LLM processing with citations."""
    
    def __init__(self, 
                 chunk_size_tokens: int = 1000,
                 overlap_tokens: int = 100):
        """
        Initialize chunker.
        
        Args:
            chunk_size_tokens: Target size of each chunk in tokens
            overlap_tokens: Number of tokens to overlap between chunks
        """
        self.chunk_size_tokens = chunk_size_tokens
        self.overlap_tokens = overlap_tokens
    
    def chunk_transcript(self, 
                        normalized_text: str,
                        turns: List[Dict] = None) -> List[Dict]:
        """
        Chunk transcript into processable segments.
        
        Args:
            normalized_text: Full normalized transcript text
            turns: Optional list of structured turns from API
        
        Returns:
            List of chunk dicts with:
                - chunk_index: int
                - text: str chunk content
                - start_char: int offset
                - end_char: int offset
                - speaker: optional str
                - section: prepared|qa|unknown
                - avg_turn_sentiment: optional float
        """
        # TODO: Implement chunking logic
        # MVP: chunk by speaker turns, then by paragraph if too long
        raise NotImplementedError("Chunking logic pending")
    
    def estimate_token_count(self, text: str) -> int:
        """
        Estimate token count for text.
        
        Args:
            text: Input text
        
        Returns:
            Estimated token count
        """
        # Simple heuristic: ~4 chars per token for English
        return len(text) // 4
