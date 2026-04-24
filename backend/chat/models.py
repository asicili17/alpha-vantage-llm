from django.db import models
import uuid


class Conversation(models.Model):
    """
    Represents a conversation session with the chat agent.
    Tracks conversation state and associates messages with a specific transcript context.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    current_transcript = models.ForeignKey(
        'transcripts.Transcript',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Conversation {self.id} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"


class Message(models.Model):
    """
    Represents a single message in a conversation.
    Can be from 'user' or 'assistant'.
    """
    ROLE_CHOICES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    content = models.TextField()
    citations = models.JSONField(null=True, blank=True)  # List of {chunk_id, short_quote}
    message_index = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['message_index']
        unique_together = [('conversation', 'message_index')]
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}..."
