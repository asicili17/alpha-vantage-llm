"""
JSON schemas for LLM extraction tasks.

Defines structured output schemas for OpenAI function calling / response_format.
"""

# Extraction schema for earnings call analysis
# This schema defines the structure for extracting key metrics, guidance, risks, and tone
EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {
            "type": "string",
            "description": "Company name as mentioned in the transcript"
        },
        "period": {
            "type": "string",
            "description": "Reporting period (e.g., Q1 2024, FY 2023)"
        },
        "key_metrics": {
            "type": "array",
            "description": "List of explicitly mentioned financial or operational metrics",
            "items": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Metric name (e.g., 'Revenue', 'EPS', 'Active Users')"
                    },
                    "value": {
                        "type": "string",
                        "description": "Metric value as stated (e.g., '$1.2B', '15%', '100M')"
                    },
                    "unit": {
                        "type": ["string", "null"],
                        "description": "Unit of measurement if applicable (e.g., 'USD', '%', 'users')"
                    },
                    "context": {
                        "type": "string",
                        "description": "Brief context around this metric (e.g., 'up 20% YoY')"
                    },
                    "citation_chunk_id": {
                        "type": "string",
                        "description": "UUID of the chunk where this metric was found"
                    }
                },
                "required": ["name", "value", "context", "citation_chunk_id"],
                "additionalProperties": False
            }
        },
        "guidance": {
            "type": "array",
            "description": "List of forward-looking guidance statements",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {
                        "type": "string",
                        "description": "Metric being guided (e.g., 'Revenue', 'Operating Margin')"
                    },
                    "range_or_value": {
                        "type": "string",
                        "description": "Guided value or range (e.g., '$500M-$600M', '10-12%')"
                    },
                    "timeframe": {
                        "type": "string",
                        "description": "Time period for guidance (e.g., 'Q2 2024', 'Full Year 2024')"
                    },
                    "qualifiers": {
                        "type": ["string", "null"],
                        "description": "Any qualifiers or conditions (e.g., 'excluding one-time charges')"
                    },
                    "citation_chunk_id": {
                        "type": "string",
                        "description": "UUID of the chunk where this guidance was found"
                    }
                },
                "required": ["metric", "range_or_value", "timeframe", "citation_chunk_id"],
                "additionalProperties": False
            }
        },
        "risks": {
            "type": "array",
            "description": "List of explicitly mentioned risks or challenges",
            "items": {
                "type": "object",
                "properties": {
                    "risk": {
                        "type": "string",
                        "description": "Brief description of the risk or challenge"
                    },
                    "context": {
                        "type": "string",
                        "description": "Context or explanation provided around this risk"
                    },
                    "severity_hint": {
                        "type": ["string", "null"],
                        "description": "Indication of severity if stated (e.g., 'material', 'manageable')"
                    },
                    "citation_chunk_id": {
                        "type": "string",
                        "description": "UUID of the chunk where this risk was mentioned"
                    }
                },
                "required": ["risk", "context", "citation_chunk_id"],
                "additionalProperties": False
            }
        },
        "tone": {
            "type": "object",
            "description": "Overall tone/sentiment of the transcript",
            "properties": {
                "label": {
                    "type": "string",
                    "enum": ["positive", "neutral", "negative", "mixed"],
                    "description": "Overall tone classification"
                },
                "rationale": {
                    "type": "string",
                    "description": "Brief explanation for the tone assessment"
                },
                "citation_chunk_ids": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "UUIDs of chunks supporting this tone assessment"
                }
            },
            "required": ["label", "rationale", "citation_chunk_ids"],
            "additionalProperties": False
        }
    },
    "required": ["company", "period", "key_metrics", "guidance", "risks", "tone"],
    "additionalProperties": False
}
