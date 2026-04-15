# Architecture Diagram: Earnings Call Analysis LLM Flow

## Full System Flowchart

```mermaid
flowchart TD
    Start([User types message<br/>e.g., Summarize AAPL 2024Q2])
    
    Start --> ParseMessage[Parse message with regex<br/>Extract: symbol, quarter, intent]
    
    ParseMessage --> RegexSuccess{Regex<br/>successful?}
    
    RegexSuccess -->|No| UseNano[Use nano LLM<br/>to classify message]
    UseNano --> ParamsParsed
    
    RegexSuccess -->|Yes| ParamsParsed[Parameters extracted:<br/>symbol, quarter, intent]
    
    ParamsParsed --> CheckParams{Have both<br/>symbol & quarter?}
    
    CheckParams -->|No| AskClarification[Return clarification question<br/>to user: Which quarter?]
    AskClarification --> WaitUser[Wait for user response]
    WaitUser --> Start
    
    CheckParams -->|Yes| CheckTranscriptCache{Transcript in<br/>DB cache?}
    
    CheckTranscriptCache -->|Yes| LoadCached[Load transcript + chunks<br/>from database]
    LoadCached --> RouteIntent
    
    CheckTranscriptCache -->|No| CallMCP[Call Alpha Vantage MCP<br/>get_earnings_call_transcript]
    
    CallMCP --> NormalizeText[Normalize speaker turns<br/>to formatted text]
    
    NormalizeText --> ChunkText[Chunk transcript<br/>~800-1200 tokens/chunk<br/>with overlap]
    
    ChunkText --> PersistTranscript[Persist transcript + chunks<br/>to database]
    
    PersistTranscript --> RouteIntent{What is<br/>the intent?}
    
    RouteIntent -->|summarize| CheckSummaryCache{Summary<br/>artifact cached?}
    RouteIntent -->|extract| CheckExtractCache{Extraction<br/>artifact cached?}
    RouteIntent -->|qa| SelectChunks[Select top-K chunks<br/>keyword scoring + section boost]
    
    CheckSummaryCache -->|Yes| ReturnCachedSummary[Return cached summary]
    ReturnCachedSummary --> BuildResponse
    
    CheckSummaryCache -->|No| MapSummarize[MAP: For each chunk<br/>mini LLM: summarize → bullets]
    
    MapSummarize --> ReduceSummarize[REDUCE: mini LLM<br/>merge all chunk summaries]
    
    ReduceSummarize --> CacheSummary[Store summary artifact<br/>in database]
    CacheSummary --> BuildResponse
    
    CheckExtractCache -->|Yes| ReturnCachedExtract[Return cached extraction]
    ReturnCachedExtract --> BuildResponse
    
    CheckExtractCache -->|No| MapExtract[MAP: For each chunk<br/>mini LLM: extract metrics/risks/guidance]
    
    MapExtract --> ReduceExtract[REDUCE: mini LLM<br/>merge with citations]
    
    ReduceExtract --> CacheExtract[Store extraction artifact<br/>in database]
    CacheExtract --> BuildResponse
    
    SelectChunks --> AnswerQuestion[mini LLM: answer question<br/>grounded in top-K chunks only<br/>with required citations]
    
    AnswerQuestion --> BuildResponse[Build response object:<br/>assistant_message, citations?]
    
    BuildResponse --> RenderUI[React UI renders:<br/>- Message<br/>- Inline extract output<br/>- Citations as expandable sources]
    
    RenderUI --> End([Display to user])
    
    style Start fill:#e1f5e1,color:#111,stroke:#2e7d32,stroke-width:2px
    style End fill:#e1f5e1,color:#111,stroke:#2e7d32,stroke-width:2px
    style CallMCP fill:#fff4e6,color:#111,stroke:#ef6c00,stroke-width:2px
    style UseNano fill:#e3f2fd,color:#111,stroke:#1565c0,stroke-width:2px
    style MapSummarize fill:#e3f2fd,color:#111,stroke:#1565c0,stroke-width:2px
    style ReduceSummarize fill:#e3f2fd,color:#111,stroke:#1565c0,stroke-width:2px
    style MapExtract fill:#e3f2fd,color:#111,stroke:#1565c0,stroke-width:2px
    style ReduceExtract fill:#e3f2fd,color:#111,stroke:#1565c0,stroke-width:2px
    style AnswerQuestion fill:#e3f2fd,color:#111,stroke:#1565c0,stroke-width:2px
    style CheckTranscriptCache fill:#fce4ec,color:#111,stroke:#ad1457,stroke-width:2px
    style CheckSummaryCache fill:#fce4ec,color:#111,stroke:#ad1457,stroke-width:2px
    style CheckExtractCache fill:#fce4ec,color:#111,stroke:#ad1457,stroke-width:2px
```

## Cost-Saving Notes

- **Caching layers:**
  - Transcript cache: `(symbol, quarter)` → avoid re-fetching from MCP
  - Chunk cache: tied to `transcript_id` → avoid re-chunking
  - Artifact cache: `(transcript_id, intent, model, prompt_version)` → avoid re-running expensive LLM calls

- **Model usage (MVP - all mini):**
  - Parser: regex first, nano only if needed
  - Summarize: mini (map) + mini (reduce)
  - Extract: mini (map) + mini (reduce)
  - Q&A: mini
  - Chunk selection: heuristic scoring (free), optional nano rerank

- **Upgrade path:**
  - If Q&A quality is weak: swap only Q&A final answer from mini → GPT-5.4
  - Keep summarize/extract on mini

## Data Flow Summary

1. **User message** → parsed into `(symbol, quarter, intent)`
2. **Transcript fetch** → MCP call if cache miss → normalize + chunk → persist
3. **Intent routing** → summarize | extract | qa
4. **LLM pipeline** → always check cache first, use mini (MVP), require citations
5. **Response** → structured JSON with text output and optional citations
6. **UI render** → ChatGPT-like display with expandable sources
