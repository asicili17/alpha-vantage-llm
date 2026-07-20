# Earnings Call Analysis Backend

Django backend for the earnings call analysis agent.

## Setup

1. **Create and activate virtual environment:**
   ```bash
   python -m venv venv
   .\venv\Scripts\Activate.ps1  # Windows PowerShell
   # or
   source venv/bin/activate  # Linux/Mac
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Create `.env` file:**
   Copy `.env.example` to `.env` and fill in your API keys:
   ```bash
   cp .env.example .env
   ```

4. **Run migrations:**
   ```bash
   python manage.py migrate
   ```

5. **Create superuser (optional):**
   ```bash
   python manage.py createsuperuser
   ```

6. **Run development server:**
   ```bash
   python manage.py runserver
   ```

## Project Structure

```
backend/
├── config/              # Django project settings
├── transcripts/         # Transcript models and services
│   └── services/        # - fetch_alpha_vantage.py (Alpha Vantage REST client + entity resolution)
│                        # - chunking.py (text chunking and retrieval)
├── agent/               # LLM orchestration
│   └── services/        # - qa.py (grounded Q&A with citations)
│                        # - summarize.py (MAP/REDUCE summarization)
│                        # - prompts.py (all LLM prompt templates)
│                        # - formatting.py (output formatting)
├── chat/                # Chat conversation models and orchestration
│   ├── models.py        # - Conversation, Message models
│   ├── views.py         # - Chat API endpoint
│   └── services/        # - __init__.py (chat orchestrator)
│                        # - query_understanding.py (LLM query parser)
│                        # - query_schema.py (ParsedQuery dataclass)
│                        # - session_state.py (conversation context)
│                        # - clarification.py (clarification handling)
│                        # - query_logging.py (query logging)
├── api/                 # Additional REST API endpoints
├── tests/               # Test suites
│   ├── test_query_understanding.py (19 tests)
│   └── test_fetch_alpha_vantage.py (16 tests)
└── manage.py
```

## Key Components

### Query Understanding Pipeline

The system uses a sophisticated LLM-powered query understanding pipeline:

1. **Semantic Parsing** (`query_understanding.py`): OpenAI GPT-4o-mini parses natural language into structured intent
2. **Entity Resolution** (`fetch_alpha_vantage.py`):
   - Company names → ticker symbols via Alpha Vantage SYMBOL_SEARCH
   - Relative periods ("latest") → concrete quarters via availability probing
3. **Session Context** (`session_state.py`): Carries forward ticker/quarter from previous messages
4. **Clarification** (`clarification.py`): Asks for missing information when needed
5. **Validation**: Deterministic validation ensures safe execution

### Example Flow

```python
User: "Summarize Apple's latest earnings call"

1. LLM Parser: intent='summarize', company_name='Apple', relative_period='latest'
2. Entity Resolution: 'Apple' → 'AAPL', 'latest' → '2024Q2' (via probing)
3. Execution: Fetch AAPL 2024Q2 transcript → MAP/REDUCE summarization
4. Response: AI-generated summary with key points
```

## Testing

Run the comprehensive test suite:

```bash
# All tests (35 total)
python manage.py test

# Query understanding tests only (19 tests)
python manage.py test chat.services.tests.test_query_understanding

# Entity resolution tests only (16 tests)
python manage.py test transcripts.services.tests.test_fetch_alpha_vantage
```

## Environment Variables

See `.env.example` for all required environment variables.

Key variables:
- `OPENAI_API_KEY`: OpenAI API key for LLM calls
- `ALPHAVANTAGE_API_KEY`: Alpha Vantage API key for transcript data
- `DEBUG`: Set to `False` in production
