# DocDeclutter – Metro Document Automation

> An enterprise-grade, agentic AI platform that automates document processing, multi-agent classification, structured information extraction, priority assessment, department routing, and human-in-the-loop review for metro rail organisations.

---

## Architecture Overview

```
                      ┌───────────────────────────────────────┐
                      │    React 18 + TypeScript Frontend     │
                      │   (Dashboard, Upload, Review, Docs)   │
                      └──────────────────┬────────────────────┘
                                         │ Axios REST API
                                         ▼
                      ┌───────────────────────────────────────┐
                      │      FastAPI High-Performance API     │
                      └────────┬───────────────────┬──────────┘
                               │                   │
         ┌─────────────────────┴──────┐     ┌─────┴─────────────────────┐
         │ Dual-Mode Storage Layer    │     │ Text Extraction Engine    │
         │ - Local Disk (Uploads/JSON)│     │ - PyMuPDF (Digital PDFs)  │
         │ - Supabase Storage & DB    │     │ - Tesseract OCR (Scanned) │
         └────────────────────────────┘     └─────────────┬─────────────┘
                                                          │ Text
                                                          ▼
                                    ┌───────────────────────────────────┐
                                    │    LangGraph Multi-Agent Engine   │
                                    │  - Document Classification Agent  │
                                    │  - Information Extraction Agent   │
                                    │  - Priority Assessment Agent      │
                                    │  - Department Routing Agent       │
                                    │  - Human-in-the-Loop Review Node  │
                                    └───────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Description |
|-------|------------|-------------|
| **Frontend** | React 18, Vite, TypeScript, Tailwind CSS | Responsive dashboard, upload queue, live OCR text viewer, AI modal, and human review modal |
| **Backend** | Python 3.12, FastAPI, Uvicorn | RESTful API, asynchronous execution, validation schemas with Pydantic |
| **OCR & PDF** | PyMuPDF (fitz), Tesseract OCR, Pillow | High-speed digital text extraction with automatic OCR fallback for scanned documents and images |
| **Agentic AI** | LangGraph, LangChain Core | Multi-agent DAG with parallel execution, conditional routing, and persistent SQLite checkpointing |
| **LLM** | Google Gemini (gemini-2.5-flash / gemini-3.5-flash-lite) | Automatic model fallback, retry handling, and JSON schema-conforming generation |
| **Storage (Dual-Mode)** | Local Filesystem + JSON / Supabase Cloud | Operates 100% locally by default; seamlessly connects to Supabase Storage & PostgreSQL when configured |

---

## Project Structure

```
DocDeclutter/
├── frontend/                     # React + Vite + TypeScript Client
│   ├── src/
│   │   ├── components/           # Navbar, AIAnalysisModal, HumanReviewModal
│   │   ├── pages/                # Dashboard, Upload, Documents, NotFound
│   │   ├── context/              # Toast notification context
│   │   ├── lib/                  # Axios API instance with VITE_API_BASE_URL
│   │   └── types/                # TypeScript interfaces for API schemas
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
│
├── backend/                      # Python FastAPI Application
│   ├── app/
│   │   ├── api/v1/endpoints/     # Documents, health, OCR & AI diagnostics
│   │   ├── agents/               # LangGraph multi-agent nodes, state, prompts, graph
│   │   ├── services/             # Document, OCR, Gemini, and Supabase services
│   │   ├── schemas/              # Pydantic request & response models
│   │   └── core/                 # Settings and CORS configuration
│   ├── migrations/               # Supabase PostgreSQL schema & bucket setup (SQL)
│   ├── scripts/                  # Safe cloud migration utility (migrate_to_supabase.py)
│   ├── uploads/                  # Local uploaded files storage (.gitkeep)
│   ├── extracted_text/           # Local extracted text storage (.gitkeep)
│   ├── data/                     # Local metadata (documents.json) & SQLite checkpoints
│   ├── requirements.txt          # Python dependencies
│   ├── test_integration.py       # Core integration test suite (50 tests)
│   ├── test_agentic_workflow.py  # LangGraph multi-agent test suite
│   ├── test_supabase_integration.py # Supabase dual-mode test suite
│   └── test_pre_deployment.py    # Pre-deployment verification suite
│
├── .env.example                  # Environment template
├── .gitignore                    # Excludes secrets, uploads, .venv, node_modules
└── README.md                     # Documentation
```

---

## Local Setup & Quick Start

### 1. Prerequisites
* **Node.js**: v18.0.0 or higher
* **Python**: v3.12 or higher
* **Tesseract OCR** *(Optional on Windows; PyMuPDF handles all digital PDFs natively)*:
  * Windows: UB-Mannheim Tesseract OCR installer or `winget install UB-Mannheim.TesseractOCR`
  * Linux: `sudo apt-get install tesseract-ocr`

### 2. Configure Environment
Create `backend/.env` from `.env.example`:
```bash
cp .env.example backend/.env
```
Populate your Gemini API key (free from [Google AI Studio](https://aistudio.google.com/app/apikey)):
```env
GEMINI_API_KEY=your_actual_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
```

*(Note: Supabase credentials are optional. If left blank, DocDeclutter will automatically use local storage).*

### 3. Start Backend
```bash
cd backend
python -m venv .venv

# Windows (PowerShell):
.\.venv\Scripts\Activate.ps1
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
Backend API will be available at: `http://127.0.0.1:8000`
Swagger interactive docs: `http://127.0.0.1:8000/api/docs`

### 4. Start Frontend
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Open your browser at: `http://localhost:5173`

---

## Running Verification & Tests

All test suites can be executed from the `backend/` directory:

```bash
cd backend

# 1. Pre-deployment End-to-End Audit (Upload, OCR, Download, Delete, Persistence)
python test_pre_deployment.py

# 2. Comprehensive Core Integration Tests (50 tests)
python test_integration.py

# 3. LangGraph Multi-Agent & Human-in-the-Loop Tests
python test_agentic_workflow.py

# 4. Supabase Dual-Mode & Fallback Tests
python test_supabase_integration.py
```

Frontend build check:
```bash
cd frontend
npm run build
```

---

## Deployment Configuration (Render)

### Backend (Web Service)
* **Environment**: Python 3
* **Build Command**: `pip install -r backend/requirements.txt`
* **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --app-dir backend`
* **Environment Variables**:
  * `PYTHON_VERSION`: `3.12.4`
  * `GEMINI_API_KEY`: *(Your key)*
  * `GEMINI_MODEL`: `gemini-2.5-flash`
  * `ALLOWED_ORIGINS`: `https://<your-frontend-service>.onrender.com,http://localhost:5173`
  * `SUPABASE_URL`: *(Optional – for persistent cloud storage on Render)*
  * `SUPABASE_SERVICE_ROLE_KEY`: *(Optional – for persistent cloud storage on Render)*

### Frontend (Static Site)
* **Build Command**: `npm run build`
* **Publish Directory**: `dist`
* **Root Directory**: `frontend`
* **Environment Variables**:
  * `VITE_API_BASE_URL`: `https://<your-backend-service>.onrender.com`

---

## Licence

MIT License. Developed for the Metro Document Automation Project.
