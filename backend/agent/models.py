from django.db import models
import uuid

from transcripts.models import Transcript


class Artifact(models.Model):
    """
    Stores cached LLM outputs (summaries, extractions) for transcripts.
    Keyed by (transcript, artifact_type, model, prompt_version) for cache invalidation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(
        Transcript,
        on_delete=models.CASCADE,
        related_name="artifacts"
    )
    artifact_type = models.CharField(max_length=50)  # summary | extraction
    model = models.CharField(max_length=100)
    prompt_version = models.CharField(max_length=20, default="v1")
    content = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [("transcript", "artifact_type", "model", "prompt_version")]
        
    def __str__(self):
        return f"{self.artifact_type} for {self.transcript} (v{self.prompt_version})"
