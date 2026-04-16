# DocuMind AI

> **An intelligent, production-grade RAG (Retrieval-Augmented Generation) system for document question answering — built with hybrid search, cross-encoder reranking, citation enforcement, and a real-time TruLens evaluation pipeline.**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-18-61DAFB?style=flat&logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=flat&logo=vite&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini_API-2.5_Flash-4285F4?style=flat&logo=google&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-FF6B35?style=flat)
![License](https://img.shields.io/badge/License-MIT-green?style=flat)

---

## 🔥 New Production Features

- **Streaming Generation (SSE)**: Real-time, token-by-token response delivery for a low-latency chat experience.
- **Complete Response Guard**: Proprietary post-processing that prevents mid-sentence truncation. If the LLM is cut off by token limits, the system automatically rolls back to the last valid punctuation or regenerates a concise replacement.
- **Evaluation Dashboard**: Integrated frontend monitoring of TruLens metrics (Faithfulness, Relevance, Correctness) with historical trend analysis.
- **Lazy Load Optimization**: Singleton-based dependency injection with lazy imports, enabling backend reloads in **under 2 seconds**.

---

## 📖 Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Architecture](#system-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Environment Variables](#environment-variables)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Running with Docker](#running-with-docker)
- [API Reference](#api-reference)
- [RAG Pipeline Deep Dive](#rag-pipeline-deep-dive)
- [Evaluation & Quality Gates](#evaluation--quality-gates)
- [Monitoring & Observability](#monitoring--observability)
- [Scripts](#scripts)
- [Running Tests](#running-tests)
- [Roadmap](#roadmap)

---

## Overview

DocuMind AI lets you upload documents (PDF, DOCX, TXT) and ask natural language questions about them. Unlike a simple keyword search, it uses a multi-stage RAG pipeline to retrieve the most relevant context, re-rank it using a cross-encoder model, generate grounded answers via Google Gemini, and verify every claim against the source material before returning it to the user.

The system is built for production: structured JSON logging, request metrics, user feedback collection, a RAGAS evaluation pipeline, and a CI quality gate are all first-class features — not afterthoughts.

---

## Key Features

**Document Ingestion**
- Upload PDF, DOCX, and TXT files via the UI or API
- Duplicate detection — files already ingested are skipped automatically
- Force re-ingest flag for updated documents
- Smart text chunking with configurable size and overlap

**Hybrid Retrieval**
- BM25 keyword search (persisted to disk with `rank-bm25`)
- Dense vector search (ChromaDB + Gemini embeddings)
- Reciprocal Rank Fusion (RRF) merges both ranked lists into one
- Multi-query retrieval: Gemini rewrites the question into multiple variants and retrieves across all of them

**Reranking**
- Cross-encoder model (`ms-marco-MiniLM-L-6-v2`) reranks candidates by true query-chunk relevance
- Score normalization ensures consistent thresholding

**Answer Generation**
- Google Gemini 2.5 Flash generates answers strictly from retrieved context
- Structured prompt enforces inline citations in `[Source: file.pdf, Page: N]` format
- Phantom citation detection flags hallucinated sources

**Verification**
- LLM-based answer verification checks every claim against retrieved chunks
- Support ratio, confidence score, and unsupported claim list are returned alongside the answer

**Evaluation**
- RAGAS evaluation pipeline: faithfulness, context relevance, answer correctness
- Golden dataset management with deduplication
- CI quality gate blocks deployment when metric thresholds are not met

**Monitoring**
- Structured JSON logging via `structlog` with daily rotating log files
- Per-request metrics: latency (p50/p95/p99), token usage, cost, retrieval methods
- User feedback (thumbs up / thumbs down) with comments
- Positive feedback can be automatically promoted to the golden evaluation dataset

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                          Frontend (React)                       │
│         Upload Docs │ Ask Questions │ View Sources │ Dashboard  │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP / REST
┌─────────────────────────────▼───────────────────────────────────┐
│                        FastAPI Backend                          │
│   /query    /ingest    /feedback    /metrics    /health         │
└────┬────────────┬──────────────┬──────────────┬────────────────┘
     │            │              │              │
     ▼            ▼              ▼              ▼
┌─────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐
│   RAG   │ │Ingestion │ │ Feedback │ │   Metrics   │
│Pipeline │ │Pipeline  │ │  Store   │ │   Tracker   │
└────┬────┘ └────┬─────┘ └──────────┘ └─────────────┘
     │           │
     ▼           ▼
┌─────────────────────────────────────────────────────────────────┐
│                         RAG Pipeline                            │
│                                                                 │
│  Query ──► QueryRewriter ──► MultiQuery ──► HybridRetriever    │
│                                                  │              │
│                              ┌───────────────────┤             │
│                              ▼                   ▼             │
│                         BM25 Index          ChromaDB           │
│                         (BM25Okapi)     (Gemini Embeddings)    │
│                              │                   │             │
│                              └────────┬──────────┘             │
│                                       ▼                        │
│                              RRF Merge & Deduplicate           │
│                                       │                        │
│                                       ▼                        │
│                           CrossEncoder Reranker                │
│                                       │                        │
│                                       ▼                        │
│                              PromptBuilder                     │
│                                       │                        │
│                                       ▼                        │
│                             Gemini 2.5 Flash                   │
│                                       │                        │
│                                       ▼                        │
│                             AnswerVerifier                     │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **LLM** | Google Gemini 2.5 Flash |
| **Embeddings** | Google Gemini Embedding (`gemini-embedding-001`) |
| **Vector DB** | ChromaDB (persistent, local) |
| **Keyword Search** | BM25 via `rank-bm25` |
| **Reranker** | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| **Backend** | FastAPI, Uvicorn |
| **Frontend** | React 18, Vite, TailwindCSS |
| **State Management** | Zustand |
| **Data Fetching** | TanStack Query (React Query) |
| **Animations** | Framer Motion |
| **Charts** | Recharts |
| **Icons** | Lucide React |
| **Evaluation** | RAGAS |
| **Logging** | structlog |
| **PDF Parsing** | pdfplumber + pypdf (fallback) |
| **Config** | pydantic-settings, python-dotenv |
| **Containerization** | Docker |

---

## Project Structure

```
documind_ai/
├── backend/
│   ├── api/
│   │   ├── main.py                  # FastAPI app, lifespan, CORS
│   │   ├── dependencies.py          # Singleton dependency injection
│   │   └── routes/
│   │       ├── query.py             # POST /query — main RAG endpoint
│   │       ├── ingest.py            # POST /ingest/file, /ingest/directory
│   │       ├── feedback.py          # POST /feedback, GET /feedback/summary
│   │       └── metrics.py           # GET /metrics, /metrics/latency, /metrics/daily
│   │
│   ├── ingestion/
│   │   ├── document_loader.py       # PDF, DOCX, TXT loaders
│   │   ├── chunker.py               # Sentence-aware overlapping chunker
│   │   ├── embedder.py              # Gemini batch embedder
│   │   └── pipeline.py              # End-to-end ingestion orchestrator
│   │
│   ├── retrieval/
│   │   ├── vector_store.py          # ChromaDB wrapper (upsert, search, delete)
│   │   ├── bm25_retriever.py        # BM25 index (persisted to disk)
│   │   ├── hybrid_retriever.py      # RRF merge of BM25 + vector results
│   │   ├── query_rewriter.py        # Gemini-powered query rewriting + variants
│   │   └── multi_query.py           # Multi-query retrieval orchestrator
│   │
│   ├── reranking/
│   │   └── cross_encoder.py         # ms-marco cross-encoder reranker
│   │
│   ├── generation/
│   │   ├── prompt_builder.py        # Context assembly + citation prompt templates
│   │   ├── llm_client.py            # Gemini API wrapper with retry + cost tracking
│   │   └── answer_generator.py      # Full RAG pipeline orchestrator (RAGResponse)
│   │
│   ├── verification/
│   │   ├── citation_enforcer.py     # Citation extraction + phantom detection
│   │   └── answer_verifier.py       # LLM-based claim verification
│   │
│   ├── evaluation/
│   │   ├── golden_dataset.py        # Golden QA dataset management
│   │   ├── ragas_evaluator.py       # RAGAS evaluation runner
│   │   └── ci_gate.py               # CI/CD quality gate (pass/fail)
│   │
│   ├── monitoring/
│   │   ├── metrics_tracker.py       # Per-request metrics to JSONL
│   │   ├── feedback_store.py        # User feedback persistence
│   │   └── logger.py                # Request/response audit logger
│   │
│   ├── config/
│   │   ├── settings.py              # Pydantic settings (all env vars)
│   │   └── logging_config.py        # structlog setup
│   │
│   ├── scripts/
│   │   ├── ingest_documents.py      # CLI: ingest a file or directory
│   │   ├── generate_golden.py       # CLI: generate golden QA pairs
│   │   └── run_evaluation.py        # CLI: run RAGAS evaluation
│   │
│   ├── tests/
│   │   ├── test_ingestion.py
│   │   ├── test_retrieval.py
│   │   ├── test_generation.py
│   │   ├── test_verification.py
│   │   └── test_evaluation.py
│   │
│   ├── data/
│   │   ├── documents/               # Uploaded documents (gitignored)
│   │   ├── chroma_db/               # ChromaDB persistent storage (gitignored)
│   │   ├── bm25_index/              # BM25 pickled index (gitignored)
│   │   ├── golden_dataset/          # golden_qa.json
│   │   ├── metrics/                 # Per-day JSONL metrics files (gitignored)
│   │   ├── feedback/                # Per-day JSONL feedback files (gitignored)
│   │   └── logs/                    # Structured JSON logs (gitignored)
│   │
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── components/              # Reusable UI components
│   │   ├── pages/                   # Route-level page components
│   │   ├── store/                   # Zustand state stores
│   │   ├── hooks/                   # TanStack Query hooks
│   │   └── lib/                     # API client, utilities
│   ├── package.json
│   └── vite.config.ts
│
├── Dockerfile
├── docker-compose.yml
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites

- Python **3.11+**
- Node.js **18+**
- A **Google Gemini API key** — [get one here](https://aistudio.google.com/app/apikey)
- Docker (optional, for containerized deployment)

---

### Environment Variables

Copy the example file and fill in your values:

```bash
cp backend/.env.example backend/.env
```

**`backend/.env`**

```env
# ── Gemini ──────────────────────────────────────────────────────
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
GEMINI_EMBEDDING_MODEL=models/gemini-embedding-001
GEMINI_TEMPERATURE=0.1
GEMINI_MAX_TOKENS=8192

# ── ChromaDB ─────────────────────────────────────────────────────
CHROMA_PERSIST_DIR=data/chroma_db
CHROMA_COLLECTION_NAME=rag_documents

# ── BM25 ─────────────────────────────────────────────────────────
BM25_INDEX_DIR=data/bm25_index

# ── Chunking ─────────────────────────────────────────────────────
CHUNK_SIZE=800
CHUNK_OVERLAP=150

# ── Retrieval ────────────────────────────────────────────────────
VECTOR_SEARCH_TOP_K=10
BM25_SEARCH_TOP_K=10
FINAL_TOP_K=5
MULTI_QUERY_COUNT=3

# ── Reranker ─────────────────────────────────────────────────────
RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2

# ── Evaluation ───────────────────────────────────────────────────
GOLDEN_DATASET_PATH=data/golden_dataset/golden_qa.json
MIN_FAITHFULNESS_SCORE=0.7
MIN_CONTEXT_RELEVANCE_SCORE=0.7
MIN_ANSWER_CORRECTNESS_SCORE=0.6

# ── Monitoring ───────────────────────────────────────────────────
METRICS_LOG_DIR=data/metrics
FEEDBACK_LOG_DIR=data/feedback

# ── API Server ───────────────────────────────────────────────────
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true
LOG_LEVEL=INFO
```

> **Important:** The `.env` file is gitignored. Never commit your API key.

---

### Backend Setup

```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the API server
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`.  
Interactive API docs are at `http://localhost:8000/docs`.

---

### Frontend Setup

```bash
# 1. Navigate to the frontend directory
cd frontend

# 2. Install dependencies
npm install

# 3. Start the development server
npm run dev
```

The frontend will be available at `http://localhost:5173`.

> Make sure the backend is running first. The frontend expects the API at `http://localhost:8000` by default. Update `src/lib/api.ts` (or your API base URL config) if you change the backend port.

---

### Running with Docker

```bash
# Build and start all services
docker-compose up --build

# Run in detached mode
docker-compose up --build -d

# Stop all services
docker-compose down

# Stop and remove volumes (clears all persisted data)
docker-compose down -v
```

The frontend will be served at `http://localhost:3000` and the backend API at `http://localhost:8000`.

> Set your `GEMINI_API_KEY` in the environment or in a `.env` file at the project root before running Docker.

---

## API Reference

All endpoints are available under `http://localhost:8000`. Full interactive documentation is at `/docs`.

### Query

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/query` | Run the full RAG pipeline for a question |

**Request body:**
```json
{
  "query": "What are the main recommendations in the document?",
  "use_query_rewriting": true,
  "use_multi_query": true,
  "verify_answer": true
}
```

**Response:**
```json
{
  "success": true,
  "query": "What are the main recommendations in the document?",
  "rewritten_query": "What are the primary actionable recommendations outlined in the document?",
  "answer": "The document recommends... [Source: report.pdf, Page: 3]",
  "sources": [
    {
      "source_file": "report.pdf",
      "page_number": 3,
      "chunk_id": "abc123_p3_c0",
      "relevance_score": 0.9124,
      "content_preview": "The team recommends expanding..."
    }
  ],
  "verification": {
    "is_fully_supported": true,
    "support_ratio": 1.0,
    "confidence": 0.92,
    "citation_count": 3,
    "unsupported_claims": [],
    "has_citations": true
  },
  "metrics": {
    "total_latency_ms": 4820.5,
    "retrieval_latency_ms": 980.2,
    "reranking_latency_ms": 340.1,
    "generation_latency_ms": 3500.2,
    "input_tokens": 1445,
    "output_tokens": 210,
    "total_tokens": 1655,
    "cost_usd": 0.000207,
    "num_chunks_retrieved": 10,
    "num_chunks_used": 5,
    "num_queries_used": 3,
    "retrieval_methods": ["hybrid"]
  }
}
```

### Ingestion

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/ingest/file` | Upload and ingest a single file |
| `POST` | `/ingest/directory` | Ingest all documents from a server-side directory |
| `GET` | `/ingest/status` | Get current vector store and BM25 index stats |

**Supported file types:** `.pdf`, `.docx`, `.txt`

### Feedback

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/feedback` | Submit thumbs up / thumbs down on an answer |
| `GET` | `/feedback/summary?days=30` | Get aggregated feedback statistics |
| `GET` | `/feedback/negative?days=30` | Get all negative feedback for review |

### Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/metrics?days=7` | Full metrics dashboard |
| `GET` | `/metrics/latency?days=7` | Latency percentiles (p50 / p95 / p99) |
| `GET` | `/metrics/daily?days=7` | Per-day aggregated metrics |

### System

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/` | API info |

---

## RAG Pipeline Deep Dive

A query goes through the following stages:

```
1. Query Rewriting
   └── Gemini rewrites the original question for better retrieval precision
       and generates N variant queries (default: 3)

2. Multi-Query Hybrid Retrieval
   ├── BM25 keyword search across all query variants
   ├── Dense vector search (Gemini embeddings) across all query variants
   └── Results merged via Reciprocal Rank Fusion (RRF)

3. Cross-Encoder Reranking
   └── ms-marco MiniLM scores all candidates against the rewritten query
       and returns the top-K most relevant chunks

4. Prompt Assembly
   └── Retrieved chunks are formatted with source labels and injected
       into a structured prompt that enforces inline citations

5. Generation
   └── Gemini 2.5 Flash generates a grounded answer with citations

6. Verification
   ├── Citation extraction and phantom citation detection
   ├── LLM-based claim verification against retrieved chunks
   └── Support ratio and confidence score computed

7. Response
   └── Answer + sources + verification result + full pipeline metrics
```

**Why hybrid search?** BM25 excels at exact keyword matches (document IDs, names, codes). Vector search excels at semantic similarity. RRF fusion consistently outperforms either method alone.

**Why multi-query?** A single query phrasing may miss relevant chunks. Generating 2–3 semantically diverse variants increases recall without introducing noise, because deduplication keeps only unique chunks.

---

## Evaluation & Quality Gates

DocuMind AI includes a full RAGAS evaluation pipeline to objectively measure answer quality.

### Golden Dataset

The golden dataset lives at `data/golden_dataset/golden_qa.json` and contains manually curated or feedback-derived QA pairs. It is the ground truth for all evaluations.

```json
[
  {
    "question": "What is the main purpose of this document?",
    "ground_truth": "This document summarizes the peer review of a drought trigger model used by UN OCHA in Chad.",
    "contexts": [],
    "source_files": ["report.pdf"],
    "metadata": { "manually_created": true }
  }
]
```

### Metrics Tracked

| Metric | Threshold | Description |
|--------|-----------|-------------|
| **Faithfulness** | ≥ 0.70 | Are all answer claims grounded in the retrieved context? |
| **Context Relevance** | ≥ 0.70 | Is the retrieved context actually relevant to the question? |
| **Answer Correctness** | ≥ 0.60 | Does the answer match the ground truth semantically? |

### Running Evaluation

```bash
cd backend

# Show golden dataset stats
python scripts/run_evaluation.py --stats

# Run full evaluation
python scripts/run_evaluation.py

# Evaluate on first 10 questions only (fast check)
python scripts/run_evaluation.py --max 10

# Export positive user feedback → golden dataset, then evaluate
python scripts/run_evaluation.py --add-feedback --feedback-days 30
```

### CI Quality Gate

```bash
python evaluation/ci_gate.py

# Exits with code 0 if all metrics pass
# Exits with code 1 if any metric fails — blocks deployment
```

---

## Monitoring & Observability

### Structured Logging

All events are logged as JSON using `structlog`. Logs are written to `data/logs/rag_system_YYYYMMDD.log` with daily rotation.

```json
{
  "event": "rag_pipeline_complete",
  "query_preview": "What are the main topics...",
  "total_latency_ms": 4820.5,
  "total_tokens": 1655,
  "cost_usd": 0.000207,
  "num_sources": 4,
  "level": "info",
  "logger": "generation.answer_generator",
  "timestamp": "2026-03-27T07:30:45.905189Z"
}
```

### Metrics Dashboard

Request metrics are persisted to `data/metrics/requests_YYYY_MM_DD.jsonl`. The `/metrics` API endpoint aggregates them:

- **Latency:** p50, p95, p99, min, max, avg
- **Cost:** total and average USD per request
- **Tokens:** total and average token usage
- **Quality:** average support ratio across verified answers
- **Success rate:** percentage of non-error responses

### User Feedback Loop

```
User submits thumbs up/down  →  Saved to data/feedback/
         ↓
GET /feedback/negative       →  Engineers review what went wrong
         ↓
run_evaluation.py --add-feedback  →  Positive feedback added to golden dataset
         ↓
Evaluation score improves    →  CI gate passes
```

---

## Scripts

All scripts are run from the `backend/` directory.

### Ingest Documents

```bash
# Ingest all documents in data/documents/
python scripts/ingest_documents.py

# Ingest a specific file
python scripts/ingest_documents.py --file path/to/document.pdf

# Force re-ingest (overwrite existing)
python scripts/ingest_documents.py --force

# Ingest from a custom directory
python scripts/ingest_documents.py --dir path/to/docs/
```

### Generate Golden QA Pairs

```bash
# Run default seed questions through RAG and review each answer
python scripts/generate_golden.py

# Load questions from a text file (one per line)
python scripts/generate_golden.py --questions questions.txt

# Auto-approve all answers (no manual review)
python scripts/generate_golden.py --auto-approve

# Save to a custom path
python scripts/generate_golden.py --output path/to/golden.json
```

### Run Evaluation

```bash
python scripts/run_evaluation.py --stats          # Show dataset stats only
python scripts/run_evaluation.py                  # Full evaluation
python scripts/run_evaluation.py --max 10         # Quick test on 10 questions
python scripts/run_evaluation.py --add-feedback   # Import feedback first
```

---

## Running Tests

```bash
cd backend

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=. --cov-report=term-missing

# Run a specific test file
pytest tests/test_ingestion.py -v
pytest tests/test_generation.py -v
pytest tests/test_retrieval.py -v
pytest tests/test_verification.py -v
pytest tests/test_evaluation.py -v
```

> **Note:** Integration tests (ingestion, retrieval) require at least one document in `data/documents/` and a valid `GEMINI_API_KEY`.

---

## Roadmap

- [ ] Multi-document session context (chat history)
- [ ] Support for image extraction from PDFs
- [ ] OpenAI / Anthropic model provider support
- [ ] Streaming answer generation (SSE)
- [ ] User authentication and per-user document namespaces
- [ ] Table extraction and structured data querying
- [ ] Automated golden dataset generation via LLM
- [ ] Grafana dashboard integration for metrics

---

## License

This project is licensed under the MIT License.

---

<div align="center">
  <strong>Built by</strong> <a href="https://github.com/yourusername">Your Name</a>
  <br/>
  <em>Portfolio project showcasing production-grade RAG system design</em>
</div>
