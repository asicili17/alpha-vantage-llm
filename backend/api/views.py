"""
API views for transcript operations.
"""

import json

import httpx
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from agent.models import Artifact
from agent.services.extract import get_or_create_extraction, MODEL as EXTRACT_MODEL
from agent.services.qa import answer_question
from agent.services.summarize import get_or_create_summary, MODEL
from transcripts.models import Transcript
from transcripts.services.fetch_alpha_vantage import (
    get_or_fetch_transcript,
    TranscriptNotAvailable,
    RateLimitError
)
from .serializers import FetchTranscriptRequestSerializer, FetchTranscriptResponseSerializer


@api_view(['POST'])
def fetch_transcript(request):
    """
    Fetch earnings call transcript from Alpha Vantage.
    
    POST /api/transcripts/fetch
    Body: {symbol, quarter}
    
    Returns:
        200: {transcript_id, symbol, quarter, status}
        400: Validation error
        503: Rate limit error
    """
    # Validate request
    request_serializer = FetchTranscriptRequestSerializer(data=request.data)
    if not request_serializer.is_valid():
        return Response(
            {"error": "Invalid request", "details": request_serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    symbol = request_serializer.validated_data['symbol']
    quarter = request_serializer.validated_data['quarter']
    
    # Check if already cached
    try:
        existing = Transcript.objects.get(
            source="alphavantage",
            symbol=symbol,
            quarter=quarter
        )
        response_data = {
            "transcript_id": str(existing.id),
            "symbol": existing.symbol,
            "quarter": existing.quarter,
            "status": "cached"
        }
        # Validate response data through serializer
        response_serializer = FetchTranscriptResponseSerializer(data=response_data)
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    except Transcript.DoesNotExist:
        pass
    
    # Fetch transcript
    try:
        transcript = get_or_fetch_transcript(symbol, quarter)
        response_data = {
            "transcript_id": str(transcript.id),
            "symbol": transcript.symbol,
            "quarter": transcript.quarter,
            "status": "fetched"
        }
        # Validate response data through serializer
        response_serializer = FetchTranscriptResponseSerializer(data=response_data)
        response_serializer.is_valid(raise_exception=True)
        return Response(response_serializer.data, status=status.HTTP_200_OK)
    
    except json.JSONDecodeError as e:
        # Must be before ValueError since JSONDecodeError inherits from ValueError
        return Response(
            {"error": "Bad Gateway", "message": f"Invalid JSON response from Alpha Vantage: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    
    except ValueError as e:
        return Response(
            {"error": "Invalid input", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    except TranscriptNotAvailable as e:
        # 404: Resource not found - the transcript doesn't exist for this symbol/quarter
        return Response(
            {"error": "Transcript not available", "message": str(e)},
            status=status.HTTP_404_NOT_FOUND
        )
    
    except RateLimitError as e:
        # 503: Service temporarily unavailable due to rate limiting
        # Client should retry later (with backoff)
        return Response(
            {"error": "Rate limit exceeded", "message": str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    except httpx.HTTPError as e:
        return Response(
            {"error": "Bad Gateway", "message": f"Network error communicating with Alpha Vantage: {str(e)}"},
            status=status.HTTP_502_BAD_GATEWAY
        )
    
    except RuntimeError as e:
        # MCP errors (JSON-RPC errors)
        return Response(
            {"error": "Service Unavailable", "message": f"MCP service error: {str(e)}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    
    except Exception as e:
        return Response(
            {"error": "Internal server error", "message": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


class SummarizeView(APIView):
    """
    Generate or retrieve cached summary for a transcript.
    
    POST /api/transcripts/<uuid:pk>/summarize
    
    Returns:
        200: {artifact_id, summary, cached}
        404: Transcript not found
        500: Summarization error
    """
    
    def post(self, request, pk):
        """
        Summarize a transcript using map/reduce pipeline.
        
        Args:
            pk: Transcript UUID
            
        Returns:
            JSON response with summary artifact
        """
        # Get transcript
        try:
            transcript = Transcript.objects.get(pk=pk)
        except Transcript.DoesNotExist:
            return Response(
                {"error": "Transcript not found", "message": f"No transcript with id {pk}"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if artifact already exists (cached)
        cached = False
        try:
            artifact = Artifact.objects.get(
                transcript=transcript,
                artifact_type="summary",
                model=MODEL,
                prompt_version="v1"
            )
            cached = True
        except Artifact.DoesNotExist:
            # Need to create it
            try:
                artifact = get_or_create_summary(transcript)
            except Exception as e:
                return Response(
                    {"error": "Summarization failed", "message": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Return response
        return Response(
            {
                "artifact_id": str(artifact.id),
                "summary": artifact.content,
                "cached": cached
            },
            status=status.HTTP_200_OK
        )


class ExtractView(APIView):
    """
    Generate or retrieve cached extraction for a transcript.
    
    POST /api/transcripts/<uuid:pk>/extract
    
    Returns:
        200: {artifact_id, extraction, cached}
        404: Transcript not found
        500: Extraction error
    """
    
    def post(self, request, pk):
        """
        Extract structured information from a transcript using map/reduce pipeline.
        
        Args:
            pk: Transcript UUID
            
        Returns:
            JSON response with extraction artifact
        """
        # Get transcript
        try:
            transcript = Transcript.objects.get(pk=pk)
        except Transcript.DoesNotExist:
            return Response(
                {"error": "Transcript not found", "message": f"No transcript with id {pk}"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check if artifact already exists (cached)
        cached = False
        try:
            artifact = Artifact.objects.get(
                transcript=transcript,
                artifact_type="extraction",
                model=EXTRACT_MODEL,
                prompt_version="v1"
            )
            cached = True
        except Artifact.DoesNotExist:
            # Need to create it
            try:
                artifact = get_or_create_extraction(transcript)
            except Exception as e:
                return Response(
                    {"error": "Extraction failed", "message": str(e)},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        # Return response
        return Response(
            {
                "artifact_id": str(artifact.id),
                "extraction": artifact.content,
                "cached": cached
            },
            status=status.HTTP_200_OK
        )


class QAView(APIView):
    """
    Answer a question about a transcript using grounded Q&A.
    
    POST /api/transcripts/<uuid:pk>/qa
    Body: {question: string}
    
    Returns:
        200: {answer, citations, confidence, chunks_used}
        404: Transcript not found
        400: Invalid request (missing question)
        500: Q&A error
    """
    
    def post(self, request, pk):
        """
        Answer a question about the transcript using retrieval + LLM.
        
        Args:
            pk: Transcript UUID
            request.data.question: Question string
            
        Returns:
            JSON response with answer, citations, confidence, and chunks_used
        """
        # Validate request body
        question = request.data.get('question')
        if not question:
            return Response(
                {"error": "Invalid request", "message": "Field 'question' is required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get transcript
        try:
            transcript = Transcript.objects.get(pk=pk)
        except Transcript.DoesNotExist:
            return Response(
                {"error": "Transcript not found", "message": f"No transcript with id {pk}"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Answer question (not cached - each question is unique)
        try:
            result = answer_question(transcript, question)
        except Exception as e:
            return Response(
                {"error": "Q&A failed", "message": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Return response
        return Response(
            {
                "answer": result["answer"],
                "citations": result["citations"],
                "confidence": result["confidence"],
                "chunks_used": result["chunks_used"]
            },
            status=status.HTTP_200_OK
        )

