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
