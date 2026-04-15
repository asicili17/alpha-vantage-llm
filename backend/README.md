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
│   └── services/        # - fetch_alpha_vantage.py (MCP client)
│                        # - chunking.py (text chunking)
├── agent/               # LLM orchestration
│   └── services/        # - orchestrator.py (main pipeline)
│                        # - prompts.py (prompt templates)
│                        # - schemas.py (JSON schemas)
│                        # - retrieval.py (chunk selection)
├── chat/                # Chat conversation models
├── api/                 # REST API endpoints
└── manage.py
```

## Next Steps

1. Implement database models in `transcripts/models.py` and `chat/models.py`
2. Run `python manage.py makemigrations` and `python manage.py migrate`
3. Implement MCP client for Alpha Vantage in `transcripts/services/fetch_alpha_vantage.py`
4. Implement chunking logic in `transcripts/services/chunking.py`
5. Build API endpoints in `api/views.py`

## Environment Variables

See `.env.example` for all required environment variables.

Key variables:
- `OPENAI_API_KEY`: OpenAI API key for LLM calls
- `ALPHAVANTAGE_API_KEY`: Alpha Vantage API key for transcript data
- `DEBUG`: Set to `False` in production
