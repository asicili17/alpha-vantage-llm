"""
Prompt templates for LLM tasks.
"""

SYSTEM_PROMPT = """You are an earnings call analysis assistant. You MUST ground all answers in the provided transcript excerpts.

Rules:
- If the transcript does not contain the information, say you cannot find it.
- Prefer direct quotes for key claims (guidance numbers, risks, metrics).
- When answering questions, cite sources as an array of citations with chunk_id and short_quote.
- Do not invent numbers or company actions.

Output rules:
- For extraction tasks, output valid JSON that matches the provided schema.
- For Q&A tasks, output:
  - answer: string
  - citations: [{chunk_id: string, short_quote: string}]
  - confidence: one of [high, medium, low]
"""

# =============================================================================
# Map/Reduce Summarization Prompts
# =============================================================================

MAP_SYSTEM_PROMPT = """You are an earnings call analysis assistant. Summarize only what is explicitly stated in the transcript chunk."""

MAP_USER_PROMPT = """Task: Summarize this earnings call chunk in 3-5 concise bullet points.

Focus on:
- Financial results (revenue, profit, margins, growth rates)
- Forward guidance (forecasts, targets, expectations)
- Risks and challenges mentioned
- Strategic priorities and initiatives

Rules:
- Be specific and factual
- Include numbers when mentioned
- Do not infer or extrapolate
- Return valid JSON matching this schema: {{"bullets": [string], "mentions_guidance": boolean}}

Chunk:
{chunk_text}

Return only valid JSON, no markdown wrapping."""

REDUCE_SYSTEM_PROMPT = """You are an earnings call analysis assistant."""

REDUCE_USER_PROMPT = """Task: Merge these summaries from different parts of an earnings call into one cohesive summary.

Input summaries:
{summaries}

Instructions:
- Combine into max 10 bullet points
- Deduplicate similar facts, keeping the most specific version
- Organize by topic (financial results, guidance, risks, strategy)
- Preserve key numbers and quotes
- Return valid JSON matching this schema: {{"bullets": [string], "sections_covered": [string]}}

The sections_covered should be a list of topic areas represented (e.g., ["financial_results", "guidance", "risks", "strategy"]).

Return only valid JSON, no markdown wrapping."""

# =============================================================================
# Legacy Prompts (keeping for compatibility)
# =============================================================================

SUMMARIZATION_PROMPT = """Task: Summarize this chunk in 3–6 bullets.
Include: financial performance, guidance, risks, strategic priorities.
Keep it factual; do not infer.
Return JSON: {"bullets": [...], "mentions_guidance": bool}

Chunk:
{chunk_text}
"""

EXTRACTION_PROMPT_TEMPLATE = """Extract the following fields from the transcript context. Only include items explicitly mentioned.

Schema:
- company (string)
- period (string)
- key_metrics (array of {{name, value, unit, context, citation_chunk_id}})
- guidance (array of {{metric, range_or_value, timeframe, qualifiers, citation_chunk_id}})
- risks (array of {{risk, context, severity_hint, citation_chunk_id}})
- tone ({{label: positive|neutral|negative|mixed, rationale, citation_chunk_ids}})

Transcript chunks:
{chunks}
"""

QA_PROMPT_TEMPLATE = """Question: {question}

Context: Here are the relevant transcript chunks (with chunk_id). Use only these.

Instructions:
- Answer concisely.
- Provide citations with chunk_id + short quote.
- If evidence is insufficient, say so.

Chunks:
{chunks}
"""

# =============================================================================
# Extraction Prompts (Phase 5)
# =============================================================================

EXTRACT_MAP_SYSTEM_PROMPT = """You are an earnings call analysis assistant. Extract only explicitly stated information from the transcript chunk provided. Do not infer or extrapolate."""

EXTRACT_MAP_USER_PROMPT = """Task: Extract key information from this earnings call transcript chunk.

Extract ONLY explicitly stated items:
- key_metrics: Financial or operational metrics with specific values
- guidance: Forward-looking statements with specific numbers or ranges
- risks: Explicitly mentioned risks, challenges, or concerns
- tone: Sentiment indicators (positive language, concerns, uncertainty)

Rules:
- Only include items that are directly stated in the text
- For ALL items, set citation_chunk_id to exactly: {chunk_id}
- Return empty arrays if nothing relevant is found in this chunk
- Be precise with numbers and quotes
- For company and period, extract if mentioned; otherwise use empty string

Return valid JSON matching this schema:
{{
  "company": "string",
  "period": "string",
  "key_metrics": [
    {{"name": "string", "value": "string", "unit": "string|null", "context": "string", "citation_chunk_id": "{chunk_id}"}}
  ],
  "guidance": [
    {{"metric": "string", "range_or_value": "string", "timeframe": "string", "qualifiers": "string|null", "citation_chunk_id": "{chunk_id}"}}
  ],
  "risks": [
    {{"risk": "string", "context": "string", "severity_hint": "string|null", "citation_chunk_id": "{chunk_id}"}}
  ],
  "tone": {{
    "label": "positive|neutral|negative|mixed",
    "rationale": "string",
    "citation_chunk_ids": ["{chunk_id}"]
  }}
}}

Chunk ID: {chunk_id}

Chunk text:
{chunk_text}

Return only valid JSON, no markdown wrapping."""

EXTRACT_REDUCE_SYSTEM_PROMPT = """You are an earnings call analysis assistant. Merge multiple extraction outputs into a single comprehensive extraction."""

EXTRACT_REDUCE_USER_PROMPT = """Task: Merge these extraction outputs from different chunks of the same earnings call into one final extraction.

Input extractions:
{extractions}

Instructions:
- Combine all key_metrics, guidance, and risks arrays
- Deduplicate similar items, keeping the most specific and detailed version
- Preserve ALL citation_chunk_id values from the originals
- For company: use the first non-empty value
- For period: use the first non-empty value (or most specific if multiple)
- For tone: synthesize a single overall label based on all chunk tones
  - If mostly positive → "positive"
  - If mostly negative → "negative"  
  - If balanced or unclear → "mixed"
  - If all neutral → "neutral"
- For tone.rationale: write a brief summary explaining the overall tone
- For tone.citation_chunk_ids: collect all chunk IDs that contributed to tone assessment

Return valid JSON matching this schema:
{{
  "company": "string",
  "period": "string",
  "key_metrics": [
    {{"name": "string", "value": "string", "unit": "string|null", "context": "string", "citation_chunk_id": "string"}}
  ],
  "guidance": [
    {{"metric": "string", "range_or_value": "string", "timeframe": "string", "qualifiers": "string|null", "citation_chunk_id": "string"}}
  ],
  "risks": [
    {{"risk": "string", "context": "string", "severity_hint": "string|null", "citation_chunk_id": "string"}}
  ],
  "tone": {{
    "label": "positive|neutral|negative|mixed",
    "rationale": "string",
    "citation_chunk_ids": ["string"]
  }}
}}

Return only valid JSON, no markdown wrapping."""
