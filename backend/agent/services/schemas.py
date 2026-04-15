"""
JSON schemas for structured extraction outputs.
"""

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "company": {"type": "string"},
        "period": {"type": "string"},
        "key_metrics": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "context": {"type": "string"},
                    "citation_chunk_id": {"type": "string"}
                },
                "required": ["name", "value", "citation_chunk_id"]
            }
        },
        "guidance": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "metric": {"type": "string"},
                    "range_or_value": {"type": "string"},
                    "timeframe": {"type": "string"},
                    "qualifiers": {"type": "string"},
                    "citation_chunk_id": {"type": "string"}
                },
                "required": ["metric", "range_or_value", "citation_chunk_id"]
            }
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "risk": {"type": "string"},
                    "context": {"type": "string"},
                    "severity_hint": {"type": "string"},
                    "citation_chunk_id": {"type": "string"}
                },
                "required": ["risk", "citation_chunk_id"]
            }
        },
        "tone": {
            "type": "object",
            "properties": {
                "label": {
                    "type": "string",
                    "enum": ["positive", "neutral", "negative", "mixed"]
                },
                "rationale": {"type": "string"},
                "citation_chunk_ids": {
                    "type": "array",
                    "items": {"type": "string"}
                }
            },
            "required": ["label", "rationale"]
        }
    },
    "required": ["company", "period"]
}

QA_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_id": {"type": "string"},
                    "short_quote": {"type": "string"}
                },
                "required": ["chunk_id", "short_quote"]
            }
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"]
        }
    },
    "required": ["answer", "citations", "confidence"]
}
