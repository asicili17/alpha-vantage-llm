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


def format_extraction(content: Dict) -> str:
    """
    Format an extraction artifact into readable text.
    
    Args:
        content: Dict matching EXTRACTION_SCHEMA with company, period, key_metrics, 
                 guidance, risks, and tone
        
    Returns:
        Formatted extraction string with sections for metrics, guidance, risks, and tone
        
    Example input:
        {
            "company": "Apple Inc.",
            "period": "Q1 2024",
            "key_metrics": [{"name": "Revenue", "value": "$100B", ...}],
            "guidance": [...],
            "risks": [...],
            "tone": {"label": "positive", "rationale": "..."}
        }
        
    Example output:
        **Apple Inc. - Q1 2024 Key Insights**
        
        **Key Metrics:**
        • Revenue: $100B (up 20% YoY)
        ...
    """
    if not isinstance(content, dict):
        return str(content)  # Fallback for unexpected format
    
    company = content.get('company', 'Company')
    period = content.get('period', 'Period')
    key_metrics = content.get('key_metrics', [])
    guidance = content.get('guidance', [])
    risks = content.get('risks', [])
    tone = content.get('tone', {})
    
    lines = [f"**{company} - {period} Key Insights**", ""]
    
    # Key Metrics section
    if key_metrics:
        lines.append("**Key Metrics:**")
        for metric in key_metrics:
            name = metric.get('name', 'Unknown')
            value = metric.get('value', 'N/A')
            context = metric.get('context', '')
            if context:
                lines.append(f"• {name}: {value} ({context})")
            else:
                lines.append(f"• {name}: {value}")
        lines.append("")
    
    # Guidance section
    if guidance:
        lines.append("**Forward Guidance:**")
        for guide in guidance:
            metric = guide.get('metric', 'Unknown')
            range_value = guide.get('range_or_value', 'N/A')
            timeframe = guide.get('timeframe', '')
            qualifiers = guide.get('qualifiers', '')
            
            guidance_line = f"• {metric}: {range_value}"
            if timeframe:
                guidance_line += f" for {timeframe}"
            if qualifiers:
                guidance_line += f" ({qualifiers})"
            lines.append(guidance_line)
        lines.append("")
    
    # Risks section
    if risks:
        lines.append("**Risks & Challenges:**")
        for risk in risks:
            risk_desc = risk.get('risk', 'Unknown risk')
            context = risk.get('context', '')
            severity = risk.get('severity_hint', '')
            
            risk_line = f"• {risk_desc}"
            if severity:
                risk_line += f" (Severity: {severity})"
            lines.append(risk_line)
            if context:
                lines.append(f"  ↳ {context}")
        lines.append("")
    
    # Tone section
    if tone:
        label = tone.get('label', 'neutral')
        rationale = tone.get('rationale', '')
        lines.append("**Overall Tone:**")
        lines.append(f"• {label.capitalize()}")
        if rationale:
            lines.append(f"  ↳ {rationale}")
    
    return "\n".join(lines)


def format_artifact_content(artifact_type: str, content: Dict) -> str:
    """
    Format artifact content based on type.
    
    Args:
        artifact_type: Type of artifact ('summary' or 'extraction')
        content: Dict containing the artifact content
        
    Returns:
        Formatted string appropriate for the artifact type
    """
    if artifact_type == "summary":
        return format_summary(content)
    elif artifact_type == "extraction":
        return format_extraction(content)
    else:
        # Unknown type, return JSON representation
        import json
        return json.dumps(content, indent=2)
