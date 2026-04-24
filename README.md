# RepoGrade — AI Git Repo Task Evaluator

A production-grade, SLM-powered pipeline for evaluating GitHub repository code quality with a modern React frontend.

## Architecture

```
task-evaluation/
├── main.py                  # CLI entry point — runs the full pipeline
├── run_server.py            # FastAPI server launcher
├── requirements.txt         # Python dependencies
├── core/
│   ├── config.py            # Central config + dataclasses
│   └── logger.py            # Shared logging setup
├── stages/
│   ├── s01_cloner.py        # Stage 01 — GitPython full-clone + git stats
│   ├── s02_parser.py        # Stage 02 — tree-sitter AST parser
│   ├── s03_static.py        # Stage 03 — Semgrep/Bandit static analysis
│   ├── s07_llm.py           # Stage 07 — SLM code evaluation
│   └── s08_scorer.py        # Stage 08 — Radon/lizard metrics + scoring
├── server/
│   ├── app.py               # FastAPI application + routes
│   ├── database.py          # SQLAlchemy ORM + SQLite persistence
│   ├── schemas.py           # Pydantic request/response models
│   └── worker.py            # Background pipeline worker + SSE streaming
├── frontend/
│   ├── src/
│   │   ├── components/      # Reusable UI components
│   │   ├── pages/           # Route pages (Dashboard, Detail, History)
│   │   ├── utils/           # API client + helpers
│   │   ├── App.jsx          # Root app component
│   │   ├── main.jsx         # React entry point
│   │   └── index.css        # Design system
│   ├── index.html           # HTML entry
│   ├── vite.config.js       # Vite config with API proxy
│   └── package.json         # Node dependencies
├── data/                    # SQLite database (auto-created)
└── output/                  # CLI-generated JSON reports
```

## Quick Start

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install
```

### 3. Start the Backend API Server

```bash
python run_server.py
# Server runs at http://127.0.0.1:8000
```

### 4. Start the Frontend Dev Server

```bash
cd frontend
npm run dev
# Frontend runs at http://localhost:5173
```

### 5. Open the App

Navigate to **http://localhost:5173** in your browser.

## CLI Usage (No Frontend)

```bash
# Evaluate a public repo
python main.py --repo https://github.com/owner/repo

# Evaluate a local repo
python main.py --repo /path/to/local/repo

# Run only specific stages
python main.py --repo https://github.com/owner/repo --stages 1,2,3,7,8

# Choose LLM model
python main.py --repo https://github.com/owner/repo --model Qwen/Qwen2.5-Coder-7B-Instruct

# Save JSON report
python main.py --repo https://github.com/owner/repo --output report.json
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/evaluate` | Submit a repo for evaluation |
| GET | `/api/evaluate/{id}` | Get evaluation details |
| GET | `/api/evaluate/{id}/stream` | SSE progress stream |
| GET | `/api/evaluations` | List all evaluations |
| DELETE | `/api/evaluations/{id}` | Delete an evaluation |
| GET | `/api/health` | Health check |

## Pipeline Stages

| # | Stage | Library | Output |
|---|-------|---------|--------|
| 01 | Repo Cloner | GitPython | Full clone + git stats |
| 02 | Code Parser | tree-sitter | AST + file manifest |
| 03 | Static Analysis | Semgrep / Bandit | Security findings |
| 07 | SLM Engine | HuggingFace Transformers | Per-file AI analysis |
| 08 | Scoring | Radon + lizard | Quality scorecard |

## Tech Stack

**Backend:** Python, FastAPI, SQLAlchemy, SQLite, SSE  
**Pipeline:** GitPython, tree-sitter, Semgrep, Radon, lizard  
**LLM:** HuggingFace Transformers (Qwen2.5-Coder / DeepSeek-Coder)  
**Frontend:** React 18, Vite, React Router, Lucide Icons  
