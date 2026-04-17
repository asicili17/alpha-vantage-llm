from django.db import models
import uuid


class Transcript(models.Model):
    """
    Stores a fetched earnings call transcript.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    symbol = models.CharField(max_length=10, db_index=True)
    quarter = models.CharField(max_length=7, db_index=True)  # e.g. 2024Q1
    source = models.CharField(max_length=50, default="alphavantage")
    call_date = models.DateField(null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    raw_payload = models.JSONField(null=True, blank=True)
    raw_text = models.TextField()
    normalized_text = models.TextField()
    fetched_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [("source", "symbol", "quarter")]
        
    def __str__(self):
        return f"{self.symbol} {self.quarter} ({self.source})"


class TranscriptTurn(models.Model):
    """
    Represents a single speaker turn in a transcript.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transcript = models.ForeignKey(
        Transcript, 
        on_delete=models.CASCADE, 
        related_name="turns"
    )
    turn_index = models.PositiveIntegerField()
    speaker = models.CharField(max_length=255)
    title = models.CharField(max_length=255, null=True, blank=True)
    content = models.TextField()
    sentiment = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = [("transcript", "turn_index")]
        ordering = ["turn_index"]
        
    def __str__(self):
        return f"{self.transcript.symbol} {self.transcript.quarter} - Turn {self.turn_index}: {self.speaker}"
