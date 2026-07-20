# Architecture Diagram: Earnings Call Analysis LLM Flow

## System Overview

**ECAA (Earnings Call Analysis Agent)** is a conversational agent that helps users analyze earnings call transcripts through natural language. Users can fetch transcripts, get summaries, or ask specific questions.

## What's New: LLM-Powered Query Understanding

The system now uses **OpenAI GPT-4o-mini** to understand user queries semantically, replacing the previous keyword-based approach. This enables natural language queries like:

- \"Summarize Apple's latest earnings call\"
- \"What did the CEO say about revenue in Microsoft's last quarter?\"
- \"Fetch Tesla Q2 2024\"

### Query Understanding Pipeline

1. **Semantic Parsing**: LLM interprets user intent and extracts entities
2. **Entity Resolution**: 
   - Company names → ticker symbols (\"Apple\" → \"AAPL\")
   - Relative periods → concrete quarters (\"latest\" → \"2024Q2\")
3. **Session Context**: Carries forward ticker/quarter from previous messages
4. **Clarification**: Asks for missing information when needed
5. **Validation**: Deterministic checks ensure safe execution

## MAP/REDUCE Pattern Explained

**Problem:** Earnings transcripts are too long (~50K tokens) to fit in a single LLM call.

**Solution:** MAP/REDUCE pattern
- **MAP:** Split transcript into chunks → process each chunk independently → get N results
  - Example: 50 chunks × "summarize this chunk" = 50 mini-summaries
- **REDUCE:** Combine all chunk results → merge into final output
  - Example: Take 50 mini-summaries → "merge into one coherent summary" = 1 final summary

**Analogy:** Like having 50 people each read one chapter of a book (MAP), then one person reads all their notes and writes the final report (REDUCE).

## Key Features Implemented

✅ **Natural Language Understanding:** LLM-powered semantic query parsing  
✅ **Entity Resolution:** Company names→tickers, \"latest\"→quarters  
✅ **Multi-Intent Support:** Fetch, summarize, and Q&A capabilities  
✅ **Smart Caching:** Transcripts, chunks, and artifacts cached to minimize API costs  
✅ **Grounded Q&A:** Answers with source citations from specific chunks  
✅ **Conversation State:** Maintains context across multi-turn interactions  
✅ **Intelligent Clarification:** Asks for missing information naturally  
✅ **Error Handling:** Graceful degradation for missing transcripts and rate limits

## Full System Flowchart

```mermaid
flowchart TD
    Start([User submits message<br/>e.g., 'Summarize AAPL 2024Q2'])
    
    Start --> SendAPI[POST /api/chat/<br/>conversationId: optional<br/>message: string]
    
    SendAPI --> GetOrCreateConv{Conversation<br/>exists?}
    
    GetOrCreateConv -->|No| CreateConv[Create new Conversation<br/>in Django DB]
    GetOrCreateConv -->|Yes| LoadConv[Load existing Conversation]
    
    CreateConv --> SaveUserMsg
    LoadConv --> SaveUserMsg[Save user Message<br/>with role='user']
    
    SaveUserMsg --> ParseWithLLM[LLM Query Parser:<br/>Call GPT-4o-mini with structured output<br/>Extract: intent, symbol, company_name,<br/>quarter, relative_period, topic, etc.]
    
    ParseWithLLM --> NormalizeQuery[Normalize Fields:<br/>- Symbol → uppercase<br/>- Quarter → YYYYQN format<br/>- Validate confidence]
    
    NormalizeQuery --> ResolveEntities[Entity Resolution:<br/>1. Company name → ticker<br/>   via Alpha Vantage SYMBOL_SEARCH<br/>2. \"latest\" → quarter<br/>   via transcript probing]
    
    ResolveEntities --> ApplySessionContext[Apply Session Context:<br/>Fill missing fields from<br/>conversation.current_transcript]
    
    ApplySessionContext --> CheckClarification{Needs<br/>clarification?}
    
    CheckClarification -->|Yes| AskClarification[Generate clarification:<br/>\"I need the ticker symbol<br/>to proceed. Please provide it.\"]
    
    CheckClarification -->|No| ValidateQuery[Validate ParsedQuery:<br/>- Intent in allowed list<br/>- Quarter format correct<br/>- Symbol format valid]
    
    ValidateQuery --> RouteIntent{Route by<br/>intent}
    
    RouteIntent -->|fetch| NeedTranscript1
    RouteIntent -->|summarize| NeedTranscript2
    RouteIntent -->|qa| NeedTranscript3
    
    NeedTranscript1{Has current<br/>transcript?}
    NeedTranscript2{Has current<br/>transcript?}
    NeedTranscript3{Has current<br/>transcript?}
    
    NeedTranscript1 -->|Yes| AlreadyLoaded[Return: Already have<br/>SYMBOL QUARTER transcript]
    NeedTranscript1 -->|No| FetchTranscript1
    
    NeedTranscript2 -->|Yes| CheckSummaryCache
    NeedTranscript2 -->|No| FetchTranscript2
    
    NeedTranscript3 -->|No| AskForTranscript[Ask user to specify<br/>symbol + quarter first]
    NeedTranscript3 -->|Yes| RetrieveChunks
    
    FetchTranscript1[Alpha Vantage REST API:<br/>GET /query?function=<br/>EARNINGS_CALL_TRANSCRIPT]
    FetchTranscript2[Alpha Vantage REST API:<br/>GET /query?function=<br/>EARNINGS_CALL_TRANSCRIPT]
    
    FetchTranscript1 --> ParseTurns1[Parse structured turns<br/>to Transcript + TranscriptTurn]
    FetchTranscript2 --> ParseTurns2[Parse structured turns<br/>to Transcript + TranscriptTurn]
    
    ParseTurns1 --> ChunkIt1[Auto-chunk transcript:<br/>~1000 tokens/chunk<br/>150 token overlap<br/>detect sections prepared/qa]
    ParseTurns2 --> ChunkIt2[Auto-chunk transcript:<br/>~1000 tokens/chunk<br/>150 token overlap<br/>detect sections prepared/qa]
    
    ChunkIt1 --> SaveTranscript1[Persist Transcript<br/>+ TranscriptChunk to DB]
    ChunkIt2 --> SaveTranscript2[Persist Transcript<br/>+ TranscriptChunk to DB]
    
    SaveTranscript1 --> SetCurrentTranscript1[Set conversation.current_transcript]
    SaveTranscript2 --> SetCurrentTranscript2[Set conversation.current_transcript]
    
    SetCurrentTranscript1 --> AlreadyLoaded
    SetCurrentTranscript2 --> CheckSummaryCache
    
    CheckSummaryCache{Summary Artifact<br/>cached?}
    
    CheckSummaryCache -->|Yes| ReturnCachedSummary[Load cached summary<br/>from Artifact table]
    CheckSummaryCache -->|No| MapSummarize
    
    MapSummarize[MAP Phase:<br/>For each chunk call gpt-4o-mini<br/>with summarization prompt<br/>→ JSON with bullets]
    
    MapSummarize --> ReduceSummarize[REDUCE Phase:<br/>Merge all chunk summaries<br/>via gpt-4o-mini<br/>→ final JSON with bullets]
    
    ReduceSummarize --> SaveSummaryArtifact[Save Artifact<br/>type='summary'<br/>to DB for caching]
    
    SaveSummaryArtifact --> ReturnCachedSummary
    
    ReturnCachedSummary --> FormatSummary[Format summary JSON<br/>to readable text:<br/>bullets with headers]
    
    FormatSummary --> BuildResponse
    
    RetrieveChunks[Keyword scoring:<br/>- Count query word overlaps<br/>- Boost QA chunks for questions<br/>- Select top-K=8 chunks]
    
    RetrieveChunks --> FormatContext[Format chunks with<br/>citation markers:<br/>=== CHUNK ID: uuid ===<br/>Section: prepared/qa<br/>text...]
    
    FormatContext --> CallQA[Call gpt-4o-mini<br/>with grounded Q&A prompt:<br/>- Answer from context only<br/>- Cite sources<br/>max_tokens=2000]
    
    CallQA --> ParseQAResponse[Parse JSON response:<br/>- answer: string<br/>- citations: array<br/>- confidence: high/medium/low]
    
    ParseQAResponse --> ValidateCitations[Validate citations:<br/>- chunk_id must exist<br/>- Filter invalid ones]
    
    ValidateCitations --> BuildResponse
    
    AlreadyLoaded --> BuildResponse
    AskClarification --> BuildResponse
    AskForTranscript --> BuildResponse
    
    BuildResponse[Build response JSON:<br/>- conversation_id<br/>- assistant_message<br/>- citations array<br/>- intent<br/>- needs_clarification]
    
    BuildResponse --> SaveAssistantMsg[Save Message<br/>role='assistant'<br/>content + citations<br/>to DB]
    
    SaveAssistantMsg --> ReturnJSON[Return JSON to React:<br/>- conversation_id<br/>- assistant_message<br/>- citations<br/>- intent]
    
    ReturnJSON --> End([Response displayed to user])
    
    style Start fill:#e1f5e1,color:#111,stroke:#2e7d32,stroke-width:3px
    style End fill:#e1f5e1,color:#111,stroke:#2e7d32,stroke-width:3px
    style ParseWithLLM fill:#e3f2fd,color:#111,stroke:#1565c0,stroke-width:2px
    style ResolveEntities fill:#fff4e6,color:#111,stroke:#ef6c00,stroke-width:2px
    style FetchTranscript1 fill:#fff4e6,color:#111,stroke:#ef6c00,stroke-width:2px
    style FetchTranscript2 fill:#fff4e6,color:#111,stroke:#ef6c00,stroke-width:2px
    style MapSummarize fill:#e3f2fd,color:#111,stroke:#1565c0,stroke-width:2px
    style ReduceSummarize fill:#e3f2fd,color:#111,stroke:#1565c0,stroke-width:2px
    style CallQA fill:#e3f2fd,color:#111,stroke:#1565c0,stroke-width:2px
    style CheckSummaryCache fill:#fce4ec,color:#111,stroke:#ad1457,stroke-width:2px
    style FormatSummary fill:#f3e5f5,color:#111,stroke:#6a1b9a,stroke-width:2px
```

## User Journey Paths

ECAA supports multiple conversation flows depending on user intent. Here are the main paths a user can take:

### Path 1: Natural Language Query Flow
**Goal:** Get a summary using natural language

```
User: "Summarize Apple's latest earnings call"
  ↓
System: [LLM parses: intent='summarize', company_name='Apple', relative_period='latest']
  ↓
System: [Resolves: 'Apple' → 'AAPL', 'latest' → '2024Q2' via probing]
  ↓
System: [Fetches transcript if needed]
  ↓
System: [MAP/REDUCE summarization]
  ↓
Assistant: "Here's the summary for AAPL 2024Q2:

**Executive Summary:**
• Revenue up 15% YoY to $85.8B
• iPhone revenue grew 11% driven by strong demand
• Services revenue hit all-time high of $21.2B
• Guidance: Expecting similar growth in Q3
• Management tone optimistic about AI initiatives"
```

**Cache behavior:** Second request returns instantly from cache

---

### Path 2: Interactive Q&A Flow
**Goal:** Ask specific questions about transcript content

```
User: "Load Microsoft Q2 2024"
  ↓
System: [LLM parses: intent='fetch', company_name='Microsoft', quarter='Q2 2024']
  ↓
System: [Resolves: 'Microsoft' → 'MSFT', 'Q2 2024' → '2024Q2']
  ↓
Assistant: "Successfully fetched transcript for MSFT 2024Q2..."

User: "What did they say about Azure growth?"
  ↓
System: [LLM parses: intent='qa', topic='Azure growth']
  ↓
System: [Session context fills: symbol='MSFT', quarter='2024Q2']
  ↓
System: [Retrieves relevant chunks via keyword scoring]
  ↓
System: [Q&A with grounded citations]
  ↓
Assistant: "Azure revenue grew 29% year-over-year, driven by strong demand for AI services. The company highlighted that Azure OpenAI Service is now available in multiple regions..."

[Citations shown with expandable source chunks]

User: "What about operating margins?"
  ↓
Assistant: "Operating margins expanded to 46%, up from 44% in the prior year quarter..."
```

**Note:** Each question triggers a new LLM call (not cached), but uses fast keyword retrieval to select relevant chunks.

---

### Path 3: Clarification Flow
**Goal:** System asks for missing information

```
User: "Summarize the latest Apple earnings"
  ↓
System: [LLM parses: intent='summarize', company_name='Apple', relative_period='latest']
  ↓
System: [Resolves: 'Apple' → 'AAPL']
  ↓
System: [Probes for latest quarter: tries 2024Q4, 2024Q3, 2024Q2... finds 2024Q2]
  ↓
Assistant: "Here's the summary for AAPL 2024Q2..."

# OR if resolution fails:

User: "Summarize the earnings call"
  ↓
System: [LLM parses: intent='summarize', no company/quarter]
  ↓
System: [Clarification triggered: missing symbol AND quarter]
  ↓
Assistant: "I need the company ticker symbol and quarter (e.g., 'AAPL Q2 2024') to proceed. Please provide them."

User: "Apple Q2 2024"
  ↓
System: [LLM parses: company_name='Apple', quarter='Q2 2024']
  ↓
System: [Session context carries intent='summarize']
  ↓
System: [Resolves: 'Apple' → 'AAPL', 'Q2 2024' → '2024Q2']
  ↓
Assistant: "Here's the summary for AAPL 2024Q2..."
```

---

### Path 4: Multi-Turn Conversation Flow
**Goal:** Multiple operations on same transcript

```
User: "Fetch NVDA Q1 2024"
  ↓
Assistant: "Successfully fetched transcript for NVDA Q1 2024..."

User: "Summarize it"
  ↓
Assistant: [Returns summary - transcript already loaded]

User: "What were the data center numbers?"
  ↓
Assistant: [Q&A on same transcript]

[NEW CHAT button clicked]

User: "Summarize AMD Q1 2024"
  ↓
System: [New conversation, fresh context]
```

**Conversation State:** 
- `conversation.current_transcript` tracks active transcript
- Enables seamless follow-up questions without re-specifying symbol/quarter
- "New Chat" button resets state for clean start

---

### Path 5: Error Handling Flow
**Goal:** Graceful degradation for edge cases

```
User: "Summarize XYZ 2024Q2"
  ↓
System: [Attempts MCP fetch]
  ↓
System: [TranscriptNotAvailable exception]
  ↓
Assistant: "Sorry, I couldn't find a transcript for XYZ 2024Q2. Please verify:
• The ticker symbol is correct
• The quarter is available (earnings may not be released yet)
• Try a different quarter"
```

**Or rate limit scenario:**

```
User: "Fetch AAPL 2024Q2"
  ↓
System: [Rate limit exceeded on Alpha Vantage]
  ↓
Assistant: "Alpha Vantage API rate limit exceeded. Please try again later or upgrade to premium tier for higher limits."
```

---

### Path 6: Already Loaded Flow
**Goal:** Avoid redundant fetches

```
User: "Fetch AAPL 2024Q2"
  ↓
Assistant: "Successfully fetched transcript for AAPL 2024Q2..."

User: "Fetch AAPL 2024Q2"
  ↓
System: [Detects current_transcript already set]
  ↓
Assistant: "I already have the transcript for AAPL 2024Q2. You can ask me to summarize it or ask specific questions."
```

## Implementation Details

### Query Understanding Pipeline

#### 1. LLM Semantic Parsing
- **Method:** OpenAI GPT-4o-mini with structured JSON output
- **Input:** User message + session context (previous symbol/quarter)
- **Output:** ParsedQuery with fields:
  - `intent`: 'fetch', 'summarize', 'qa', 'clarify'
  - `symbol`: Ticker symbol if mentioned (e.g., 'AAPL')
  - `company_name`: Company name if mentioned (e.g., 'Apple')
  - `quarter`: Quarter if mentioned (e.g., 'Q2 2024')
  - `relative_period`: 'latest', 'last', 'most recent'
  - `topic`: Question topic for Q&A
  - `confidence`: 'high', 'medium', 'low'
- **Fallback:** Deterministic regex patterns as backup if LLM fails

#### 2. Entity Resolution
- **Company Name → Ticker Symbol:**
  - API: Alpha Vantage SYMBOL_SEARCH
  - Matching: bestMatch.score ≥ 0.8, type == "Equity"
  - Example: "Apple" → "AAPL" (score: 1.0)
  
- **Relative Period → Concrete Quarter:**
  - Method: Probe up to 8 quarters backwards from current date
  - Format: YYYYQN (e.g., '2024Q2')
  - Caching: Transcripts discovered during probing are cached
  - Example: "latest" → '2024Q2' (first available quarter found)

#### 3. Session Context Application
- **Source:** `conversation.current_transcript`
- **Applied:** After LLM parsing and entity resolution
- **Purpose:** Fill missing symbol/quarter from previous messages
- **Example:** 
  - Turn 1: "Load AAPL 2024Q2" → sets current_transcript
  - Turn 2: "Summarize it" → fills symbol='AAPL', quarter='2024Q2'

#### 4. Clarification Logic
- **Triggers:**
  - Missing symbol AND quarter for fetch/summarize intents
  - Missing symbol for Q&A when no current_transcript
  - Low confidence parse (though execution still proceeds)
- **Response:** Natural language request for missing information
- **Examples:**
  - "I need the company ticker symbol and quarter..."
  - "Which company's earnings call would you like to analyze?"

#### 5. Validation
- **Checks:**
  - Intent in allowed list: {'fetch', 'summarize', 'qa', 'clarify'}
  - Quarter format: YYYYQN (e.g., '2024Q2')
  - Symbol format: 1-5 uppercase letters
  - Confidence value: {'high', 'medium', 'low'}
- **Purpose:** Ensure safe execution despite LLM output

### Transcript Fetching
- **Client:** Alpha Vantage REST API via httpx
- **Endpoint:** `GET /query?function=EARNINGS_CALL_TRANSCRIPT&symbol={symbol}&year={year}&quarter={quarter}`
- **Response:** JSON with transcript text (single string, not structured turns)
- **Parsing:** Split into turns based on "Operator", "Executive", "Analyst" patterns
- **Normalization:** Convert to `Transcript` + `TranscriptTurn` Django models
- **Auto-chunking:** Immediately chunks transcript on first fetch

### Chunking Strategy
- **Target:** ~1000 tokens per chunk (max 1200)
- **Overlap:** 150 tokens between adjacent chunks
- **Section Detection:** Automatic detection of "prepared" vs "qa" sections
  - Triggers on keywords: "question and answer", "q&a session", "begin the question"
- **Storage:** `TranscriptChunk` model with fields:
  - `chunk_index`, `section`, `speaker`, `text`, `token_count`, `avg_turn_sentiment`

### MAP/REDUCE Pipelines

#### Summarization
1. **MAP Phase:**
   - Input: Individual chunk text
   - Prompt: "Extract key points as concise bullets"
   - Model: `gpt-4o-mini` (temp=0.3, max_tokens=500)
   - Output: JSON with `bullets` array and `mentions_guidance` boolean
   
2. **REDUCE Phase:**
   - Input: All chunk summaries concatenated
   - Prompt: "Merge into coherent final summary, deduplicate"
   - Model: `gpt-4o-mini` (temp=0.3)
   - Output: JSON with `bullets` array and `sections_covered`
   
3. **Caching:** Stored as `Artifact` with `type='summary'`

#### Q&A (No MAP/REDUCE)
1. **Retrieval:**
   - Keyword scoring: Count query word overlaps in chunk text
   - Section boost: +0.2 score for QA chunks if query is a question
   - Select top-K=8 chunks
   
2. **Context Formatting:**
   ```
   === CHUNK ID: {chunk.id} ===
   Section: {chunk.section}
   {chunk.text}
   ```
   
3. **LLM Call:**
   - Model: `gpt-4o-mini` (max_tokens=2000)
   - System prompt: "Answer from context only, cite sources"
   - Output: JSON with `answer`, `citations` (array of chunk_id + quote), `confidence`
   
4. **Citation Validation:** Filter citations with invalid chunk_ids

5. **No Caching:** Each question is unique, not cached

### Formatting Layer
- **Purpose:** Transform LLM JSON artifacts into human-readable text
- **Location:** `agent/services/formatting.py`
- **Functions:**
  - `format_summary()`: Bullet list with "Executive Summary" header
  - `format_artifact_content()`: Router that selects appropriate formatter

## Caching Strategy

### Three-Tier Cache System

1. **Transcript Cache:**
   - **Key:** `(symbol, quarter)` uniqueness constraint
   - **Value:** `Transcript` + related `TranscriptTurn` records
   - **Purpose:** Avoid re-fetching from Alpha Vantage MCP
   - **Invalidation:** Manual (transcripts don't change)

2. **Chunk Cache:**
   - **Key:** `transcript_id` foreign key
   - **Value:** `TranscriptChunk` records
   - **Purpose:** Avoid re-chunking on every request
   - **Lifecycle:** Created automatically on first transcript fetch, persists indefinitely

3. **Artifact Cache:**
   - **Key:** `(transcript_id, artifact_type, model, prompt_version)` uniqueness constraint
   - **Value:** `Artifact` record with JSON content
   - **Purpose:** Avoid re-running expensive MAP/REDUCE pipelines
   - **Scope:** 
     - `summary`: Cached
     - `qa`: NOT cached (questions are unique)
   - **Invalidation:** Change `prompt_version` to bust cache

### Cache Hit Patterns

**Scenario 1: First-time user asks for summary**
```
1. Fetch transcript from MCP (slow: ~2-5s)
2. Chunk transcript (fast: <1s)
3. MAP/REDUCE summarization (slow: ~10-30s depending on chunk count)
4. Cache all three levels
Total: 12-35s
```

**Scenario 2: User asks question**
```
1. Transcript cache HIT (instant)
2. Chunk cache HIT (instant)
3. Keyword retrieval (fast: <100ms)
4. Q&A LLM call (moderate: 2-5s)
Total: 2-5s (not cached, but fast)
```

**Scenario 3: Another user asks for same symbol/quarter summary**
```
1. Transcript cache HIT (instant)
2. Chunk cache HIT (instant)
3. Artifact cache HIT for summary (instant)
4. Return formatted text
Total: <1s
```

**Scenario 4: User asks question**

## Cost Analysis

### OpenAI API Usage (gpt-4o-mini)

**Per Transcript Analysis (first time, no cache):**

1. **Summarization:**
   - MAP: 50 chunks × ~1000 tokens input × 500 tokens output = 75K tokens
   - REDUCE: ~5K tokens input × ~1K tokens output = 6K tokens
   - **Total: ~81K tokens**

2. **Q&A (per question):**
   - 8 chunks × ~1000 tokens = 8K tokens input
   - Answer: ~500-2000 tokens output
   - **Total: ~9-10K tokens per question**

**Cost Estimates (gpt-4o-mini pricing):**
- Input: $0.15 / 1M tokens
- Output: $0.60 / 1M tokens

- Summarization: ~$0.02 per transcript
- Q&A: ~$0.002 per question

**With Caching:**
- Second request for same transcript+intent: $0.00 (cache hit)
- Expected 80-90% cache hit rate in production → ~80-90% cost savings

### Alpha Vantage MCP Usage

- **Rate Limit:** 25 API calls per day (free tier)
- **Cost:** $0 (free tier) or ~$50/month (premium tier for higher limits)
- **Caching Impact:** Each unique (symbol, quarter) counts as 1 API call
- **Recommendation:** Start with free tier, upgrade based on unique transcript volume

## Data Flow Summary

### Request Flow
1. **Frontend:** User submits message via POST `/api/chat/`
2. **Backend:** Django receives request → `chat/services/__init__.py:process_message()`
3. **Orchestration:** Intent detection → symbol/quarter extraction → routing
4. **Service Layer:** Execute appropriate pipeline (summarize/qa)
5. **LLM Calls:** OpenAI API with structured prompts and JSON schema responses
6. **Formatting:** Transform JSON artifacts → human-readable text
7. **Response:** Return JSON with `conversation_id`, `assistant_message`, `citations`
8. **Persistence:** All messages saved to `Message` model for conversation history

### Database Schema (Key Models)

**Transcript Flow:**
```
Transcript (symbol, quarter) 
  → TranscriptTurn (speaker, content, turn_index)
  → TranscriptChunk (text, section, token_count)
```

**Conversation Flow:**
```
Conversation (current_transcript FK)
  → Message (role, content, citations, message_index)
```

**Caching Flow:**
```
Artifact (transcript FK, artifact_type, model, prompt_version, content JSON)
```

---

## Technology Stack

### Backend (Django)
- **Framework:** Django 4.x with REST API
- **Database:** SQLite (dev) - easily upgradable to PostgreSQL
- **ORM:** Django Models for all data persistence
- **LLM Client:** OpenAI Python SDK (v1.x)
- **HTTP Client:** httpx for MCP communication
- **Key Models:**
  - `Transcript`, `TranscriptTurn`, `TranscriptChunk` (transcripts app)
  - `Conversation`, `Message` (chat app)
  - `Artifact` (agent app)

### Frontend (React)
- **Framework:** React 18 with Vite
- **UI Library:** Material-UI (MUI) v5
- **State Management:** React hooks (useState, useEffect)
- **Styling:** MUI theme + custom CSS for animations
- **HTTP Client:** Fetch API

### External Services
- **LLM:** OpenAI gpt-4o-mini via API
- **Transcript Source:** Alpha Vantage MCP server (JSON-RPC)

### Key Files Reference

**Backend:**
```
backend/
├── chat/services/__init__.py          # Main orchestration logic
├── agent/services/
│   ├── summarize.py                   # MAP/REDUCE summarization
│   ├── qa.py                          # Q&A with citations
│   ├── prompts.py                     # LLM prompt templates
│   └── formatting.py                  # JSON → readable text
├── transcripts/services/
│   ├── fetch_alpha_vantage.py         # MCP client
│   └── chunking.py                    # Chunking + retrieval
└── agent/schemas.py                   # JSON schemas for validation
```

**Frontend:**
```
frontend/src/
├── App.jsx                            # Main app with conversation state
├── api/chat.js                        # Backend API client
└── components/chat/                   # UI components for chat interface
```

---

## Future Enhancements

### Potential Improvements
1. **Semantic Search:** Replace keyword scoring with vector embeddings for better chunk retrieval
2. **Conversation History:** Persist and retrieve past conversations
3. **Export:** Generate transcripts or summaries as PDF/CSV
4. **Comparison:** Compare metrics across multiple quarters or companies
5. **Streaming Responses:** WebSocket support for real-time token streaming
6. **Multi-model Support:** Allow selection between GPT-4 and GPT-4o-mini based on query complexity
7. **Custom Prompts:** User-configurable summary styles
8. **Section Analysis:** Dedicated analysis of specific sections (guidance, risks, Q&A)
9. **Batch Processing:** Process multiple transcripts in parallel
10. **API Authentication:** Add user authentication and rate limiting

### Scalability Considerations
- **Database:** Migrate to PostgreSQL with proper indexing
- **Caching:** Add Redis for session and artifact caching
- **Queueing:** Celery for async MAP/REDUCE jobs
- **Load Balancing:** Multiple Django instances behind nginx
- **Monitoring:** Add Sentry, DataDog, or similar for error tracking and performance

---

## Conclusion

ECAA provides a fully functional conversational interface for earnings call analysis with:
- ✅ Multi-intent support (fetch, summarize, Q&A)
- ✅ Intelligent caching to minimize costs and API calls
- ✅ MAP/REDUCE pipelines for processing long documents
- ✅ Grounded Q&A with source citations and validation
- ✅ Graceful error handling and user guidance
- ✅ Conversation state management for multi-turn interactions

The system is production-ready for small-to-medium scale usage and can be scaled with the enhancements listed above.
