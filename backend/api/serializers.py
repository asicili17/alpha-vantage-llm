"""
DRF serializers for API endpoints.
"""

import re
from rest_framework import serializers


class FetchTranscriptRequestSerializer(serializers.Serializer):
    """Serializer for transcript fetch request."""
    symbol = serializers.CharField(max_length=10, required=True)
    quarter = serializers.CharField(max_length=7, required=True)
    
    def validate_symbol(self, value):
        """Validate symbol format: 1-5 uppercase letters."""
        if not re.match(r'^[A-Z]{1,5}$', value):
            raise serializers.ValidationError(
                "Symbol must be 1-5 uppercase letters (e.g., 'AAPL', 'MSFT')"
            )
        return value
    
    def validate_quarter(self, value):
        """Validate quarter format: YYYYQ{1-4}."""
        if not re.match(r'^\d{4}Q[1-4]$', value):
            raise serializers.ValidationError(
                "Quarter must be in YYYYQ{1-4} format (e.g., '2024Q2')"
            )
        return value


class FetchTranscriptResponseSerializer(serializers.Serializer):
    """Serializer for transcript fetch response."""
    transcript_id = serializers.UUIDField()
    symbol = serializers.CharField()
    quarter = serializers.CharField()
    status = serializers.CharField()
