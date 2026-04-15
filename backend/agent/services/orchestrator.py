"""
Agent orchestrator - main entry point for LLM-based analysis.

Coordinates:
- Intent routing (summarize, extract, qa)
- Model selection (nano, mini, large)
- Pipeline execution
- Artifact caching
"""

from django.conf import settings


class AgentOrchestrator:
    """Main orchestrator for transcript analysis pipelines."""
    
    def __init__(self):
        self.model_mini = settings.OPENAI_MODEL_MINI
        self.model_nano = settings.OPENAI_MODEL_NANO
        self.model_large = settings.OPENAI_MODEL_LARGE
    
    def summarize_transcript(self, transcript_id: str) -> dict:
        """
        Generate executive summary of a transcript.
        
        Args:
            transcript_id: UUID of the transcript
        
        Returns:
            dict with:
                - summary: list of bullet points
                - artifact_id: UUID of cached artifact
        """
        # TODO: Implement map/reduce summarization
        raise NotImplementedError("Summarization pipeline pending")
    
    def extract_insights(self, transcript_id: str) -> dict:
        """
        Extract structured insights (metrics, risks, guidance, tone).
        
        Args:
            transcript_id: UUID of the transcript
        
        Returns:
            dict with:
                - key_metrics: list of extracted metrics with citations
                - guidance: list of guidance statements with citations
                - risks: list of risks with citations
                - tone: tone analysis with rationale
        """
        # TODO: Implement extraction pipeline
        raise NotImplementedError("Extraction pipeline pending")
    
    def answer_question(self, transcript_id: str, question: str) -> dict:
        """
        Answer a question about the transcript.
        
        Args:
            transcript_id: UUID of the transcript
            question: User's question
        
        Returns:
            dict with:
                - answer: str
                - citations: list of {chunk_id, short_quote}
                - confidence: high|medium|low
        """
        # TODO: Implement Q&A pipeline with chunk selection
        raise NotImplementedError("Q&A pipeline pending")
