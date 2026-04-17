"""
API views for transcript operations.
"""

import json

import httpx
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

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

