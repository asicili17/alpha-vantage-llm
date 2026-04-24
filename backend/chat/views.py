"""
Chat API views.
"""

import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from chat.services import process_message
from transcripts.services.fetch_alpha_vantage import (
    TranscriptNotAvailable,
    RateLimitError
)

logger = logging.getLogger(__name__)


class ChatView(APIView):
    """
    Unified chat endpoint for conversation with the earnings call agent.
    
    POST /api/chat
    Body: {conversation_id?: string, message: string}
    
    Returns:
        200: {conversation_id, assistant_message, citations?, intent, needs_clarification}
        400: Validation error
        404: Conversation or transcript not found
        503: Rate limit error
        500: Internal error
    """
    
    def post(self, request):
        """
        Process a chat message and return assistant response.
        
        Handles intent detection, transcript fetching, and routing to
        appropriate services (summarize, extract, Q&A).
        """
        # Validate request
        message = request.data.get('message')
        if not message:
            return Response(
                {"error": "Invalid request", "details": {"message": "This field is required"}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not isinstance(message, str) or not message.strip():
            return Response(
                {"error": "Invalid request", "details": {"message": "Message must be a non-empty string"}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        conversation_id = request.data.get('conversation_id')
        if conversation_id is not None and not isinstance(conversation_id, str):
            return Response(
                {"error": "Invalid request", "details": {"conversation_id": "Must be a string UUID"}},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Process message
        try:
            result = process_message(conversation_id, message.strip())
            return Response(result, status=status.HTTP_200_OK)
        
        except ValueError as e:
            # Invalid conversation_id or other validation errors
            return Response(
                {"error": "Invalid request", "message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        except TranscriptNotAvailable as e:
            # Transcript doesn't exist for the requested symbol/quarter
            return Response(
                {"error": "Transcript not available", "message": str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
        
        except RateLimitError as e:
            # Alpha Vantage API rate limit exceeded
            return Response(
                {"error": "Rate limit exceeded", "message": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        except Exception as e:
            # Catch-all for unexpected errors
            logger.exception(f"Unexpected error in chat endpoint: {str(e)}")
            return Response(
                {"error": "Internal server error", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
