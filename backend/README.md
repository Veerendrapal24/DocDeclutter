# DocDeclutter Backend

FastAPI application for the **DocDeclutter – Metro Document Automation** project.

## Structure

```
app/
├── main.py          # FastAPI application entry point
├── core/
│   └── config.py   # Pydantic settings (reads from .env)
├── api/
│   └── v1/
│       ├── router.py        # API router aggregator
│       └── endpoints/       # Route handlers
│           ├── health.py
│           └── documents.py
├── agents/          # AI agent stubs (Phase 2)
├── services/        # Business logic layer
├── db/              # Database session & ORM models (Phase 2)
└── schemas/         # Pydantic request/response models
```

## Setup

```bash
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows PowerShell

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt  # optional dev tools

# Copy env file and fill in your values
cp ../.env.example ../.env

# Start development server
uvicorn app.main:app --reload
```

API docs available at **http://localhost:8000/api/docs**

## Environment Variables

See [`../.env.example`](../.env.example) for the full list.
