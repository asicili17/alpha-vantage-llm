"""
Chunk selection/retrieval for Q&A.

Implements:
- Keyword-based scoring
- Section preference (Q&A vs prepared remarks)
- Optional nano reranking
"""

from typing import List, Dict


class ChunkRetriever:
    """Selects relevant chunks for a given query."""
    
    def select_chunks(self, 
                     query: str,
                     chunks: List[Dict],
                     top_k: int = 10) -> List[Dict]:
        """
        Select top-K most relevant chunks for a query.
        
        Args:
            query: User's question
            chunks: All available chunks from transcript
            top_k: Number of chunks to return
        
        Returns:
            List of selected chunk dicts, ordered by relevance
        """
        # TODO: Implement keyword + section scoring
        # MVP: simple keyword matching + section boost
        raise NotImplementedError("Chunk selection pending")
    
    def score_chunk(self, query: str, chunk: Dict) -> float:
        """
        Score a chunk's relevance to the query.
        
        Args:
            query: User's question
            chunk: Chunk dict with text and metadata
        
        Returns:
            Relevance score (higher = more relevant)
        """
        # TODO: Implement scoring logic
        raise NotImplementedError("Chunk scoring pending")
