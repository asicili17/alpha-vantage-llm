# Alpha Vantage LLM - Earnings Call Analysis Agent

Intelligent conversational agent for analyzing earnings call transcripts using natural language. Powered by OpenAI GPT-4o-mini with grounded Q&A and intelligent query understanding.

## Key Features

✅ **Natural Language Understanding**: Ask questions naturally - "Summarize Apple's latest earnings call" or "What did the CEO say about revenue in Microsoft's last quarter?"

✅ **Intelligent Query Parsing**: LLM-powered semantic understanding with entity resolution:
- Company name → ticker symbol ("Apple" → "AAPL")
- Relative periods → concrete quarters ("latest" → "2024Q2")
- Automatic clarification when information is missing

✅ **Multi-Intent Support**: Fetch transcripts, get AI-generated summaries, or ask specific questions with source citations

✅ **Smart Caching**: Transcripts, chunks, and summaries cached to minimize API costs and improve response times

✅ **Grounded Q&A**: Answers backed by citations from actual transcript chunks - no hallucinations

✅ **Conversation Context**: Maintains state across multi-turn conversations for seamless follow-up questions

## Quick Start

**Backend (Django + OpenAI):**
```bash
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1  # Windows
source venv/bin/activate      # Linux/Mac
pip install -r requirements.txt
cp .env.example .env          # Add your API keys
python manage.py migrate
python manage.py runserver
```

**Frontend (React + Vite):**
```bash
cd frontend
npm install
npm run dev
```

## Example Queries

```
"Summarize Apple's latest earnings call"
"What did Microsoft say about Azure growth in Q2 2024?"
"Fetch NVDA 2024Q1"
"What were the revenue numbers?"
```

## Architecture

- **Backend**: Django REST API with OpenAI integration
- **Query Understanding**: LLM-powered semantic parsing + entity resolution
- **Data Source**: Alpha Vantage REST API for earnings transcripts
- **Frontend**: React + Material-UI chat interface
- **LLM**: GPT-4o-mini for query parsing, summarization, and Q&A

See [architecture diagram](docs/architecture-diagram.md) for detailed system flow.
