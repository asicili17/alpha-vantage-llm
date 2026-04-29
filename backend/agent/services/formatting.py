"""
Formatting utilities for converting structured artifact content to readable text.

Transforms raw JSON/dict content from LLM outputs into human-friendly formatted strings.
"""

from typing import Dict, List


def format_summary(content: Dict) -> str:
    """
    Format a summary artifact into readable text.
    
    Args:
        content: Dict with keys 'bullets' (list) and optionally 'sections_covered' (list)
        
    Returns:
        Formatted summary string with bullet points
        
    Example input:
        {
            "bullets": ["Revenue up 20% YoY", "EPS beat expectations"],
            "sections_covered": ["Financial Results", "Guidance"]
        }
        
    Example output:
        **Executive Summary:**
        
        • Revenue up 20% YoY
        • EPS beat expectations
    """
    if not isinstance(content, dict):
        return str(content)  # Fallback for unexpected format
    
    bullets = content.get('bullets', [])
    
    if not bullets:
        return "No summary content available."
    
    # Build formatted output
    lines = ["**Executive Summary:**", ""]
    
    for bullet in bullets:
        lines.append(f"• {bullet}")
    
    return "\n".join(lines)


def format_artifact_content(artifact_type: str, content: Dict) -> str:
    """
    Format artifact content based on type.
    
    Args:
        artifact_type: Type of artifact ('summary')
        content: Dict containing the artifact content
        
    Returns:
        Formatted string appropriate for the artifact type
    """
    if artifact_type == "summary":
        return format_summary(content)
    else:
        # Unknown type, return JSON representation
        import json
        return json.dumps(content, indent=2)
