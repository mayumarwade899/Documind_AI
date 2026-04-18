# DocuMind AI

> **A production-grade, self-correcting RAG (Retrieval-Augmented Generation) system for document intelligence. Built with hybrid search, cross-encoder reranking, and an automated evaluation pipeline.**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)


![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat&logo=fastapi&logoColor=white)


![Gemini](https://img.shields.io/badge/Gemini_API-2.5_Flash-4285F4?style=flat&logo=google&logoColor=white)


![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-FF6B35?style=flat)


![TruLens](https://img.shields.io/badge/TruLens-Evaluation-8CAAE6?style=flat)


---

## 📖 Overview
DocuMind AI solves the core reliability issues of RAG: **Retrieval Noise** and **Hallucinations**. It implements a multi-stage retrieval funnel (Hybrid Search + RRF + Reranking) and a 2-pass **"Verify & Repair"** generation loop to ensure every claim is strictly grounded in local documentation, preventing any leakage of external training data.

---

## Project Structure

```
documind_ai/
├── backend/
│   ├── api/
│   │   ├── main.py                  # FastAPI app entry + lifespan
│   │   ├── dependencies.py          # Singleton dependency injection
│   │   └── routes/                  # API endpoints (Query, Ingest, Eval, etc.)
│   │
│   ├── ingestion/                   # Document parsing + chunking pipeline
│   ├── retrieval/                   # Hybrid (Vec+BM25) search + Query rewriting
│   ├── reranking/                   # Cross-encoder relevance scoring
│   ├── generation/                  # RAG core (LLM Client + Answer Generator)
│   ├── verification/                # Grounding audit + Citation enforcement
│   ├── evaluation/                  # TruLens suite + Synthetic test gen
│   ├── monitoring/                  # Feedback storage + Metrics tracking
│   ├── config/                      # Pydantic settings + Structured logging
│   │
│   ├── data/
│   │   ├── documents/               # Uploaded PDFs/DOCX (gitignored)
│   │   ├── chroma_db/               # Vector store persistent data
│   │   ├── evaluation_reports/      # Detailed JSON run reports
│   │   └── feedback/                # User ratings + comments (JSONL)
│   │
│   ├── Dockerfile                   # Optimized Python container
│   └── requirements.txt             # Backend dependencies
│
├── frontend/
│   ├── src/
│   │   ├── components/              # Atomic UI elements (Buttons, Inputs)
│   │   ├── features/                # Domain-specific modules (Chat, Eval)
│   │   ├── store/                   # Zustand global state (ChatStore, etc.)
│   │   └── services/                # API client layer (TanStack Query)
│   │
│   ├── Dockerfile                   # Multi-stage build (Node -> Nginx)
│   ├── nginx.conf                   # Production Nginx SPA configuration
│   └── package.json                 # Frontend dependencies
│
├── docker-compose.yml               # Service orchestration
└── README.md                        # Documentation
```

---

## 🛠️ Tech Stack
| Layer | Technology |
|---|---|
| **LLM** | Google Gemini 2.5 Flash |
| **Embeddings** | Gemini `text-embedding-004` |
| **Vector DB** | ChromaDB (Persistent) |
| **Keyword Search** | BM25 (rank-bm25) |
| **Reranker** | Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) |
| **Backend** | FastAPI, structlog, Pydantic |
| **Frontend** | React, Vite, Zustand, Framer Motion |

---

## 📋 Response JSON Structure
Every query returns detailed verification and observability metrics:
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

## Dynamic Evaluation & Quality Gates

DocuMind AI implements a **Fully Dynamic Evaluation** strategy using TruLens. Instead of relying on a static, manually maintained "Golden Dataset," the system discovers the most relevant questions to ask by analyzing the documents currently in your knowledge base.

### How it Works

1.  **Scenario Discovery**: The system simulates diverse user personas (e.g., auditors, skeptical researchers) to generate 6 unique, factual questions per document.
2.  **Context-Aware Sampling**: It samples key snippets from the vector store to ensure every evaluation query is grounded in your specific knowledge base.
3.  **LLM-as-a-Judge**: Every answer is scored by a separate judge model against the retrieved context to calculate Faithfulness, Relevance, and Correctness.
4.  **Report Vaulting**: Evaluation results are persisted to `data/evaluation_reports/` for historical trend analysis in the dashboard.

### Metrics Tracked

| Metric | Threshold | Description |
|--------|-----------|-------------|
| **Faithfulness** | ≥ 0.70 | Are all answer claims grounded in the retrieved context? |
| **Context Relevance** | ≥ 0.70 | Is the retrieved context actually relevant to the question? |
| **Answer Correctness** | ≥ 0.60 | Does the answer match the judge's expectations of a quality response? |

---

## 📈 Monitoring & Observability

### Structured JSON Logging
All system events are logged via `structlog` for zero-configuration ingestion into modern log aggregators.
```json
{
  "event": "rag_pipeline_complete",
  "query_preview": "What are the main topics...",
  "total_latency_ms": 4820.5,
  "total_tokens": 1655,
  "cost_usd": 0.000207,
  "num_sources": 4,
  "level": "info",
  "timestamp": "2026-03-27T10:15:30Z"
}
```

### User Feedback Loop
1. User provides thumbs up/down → Saved as JSONL in `FeedbackStore`.
2. **Negative Feedback Review**: Engineers can retrieve and review failure cases via `/api/feedback/negative`.
3. **Dashboard Monitoring**: Visualizes shifts in user satisfaction against automated evaluation metrics.

---

## ⚡ Quick Start (Dockerized)
The project is fully containerized for one-click deployment:
```bash
# 1. Update backend/.env (GEMINI_API_KEY)
# 2. Start the stack
docker-compose up --build -d
```
- **UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

---

## 🚀 Documind AI — UI Preview

<img width="1365" height="595" alt="chat1" src="https://github.com/user-attachments/assets/ca844ac3-36ee-4109-a64c-2d75b437a349" />
<img width="1365" height="594" alt="chat2" src="https://github.com/user-attachments/assets/8165a6df-c691-4b1d-b21f-1043ddd95f21" />
<img width="1365" height="596" alt="chat3" src="https://github.com/user-attachments/assets/792311bf-fd27-42e4-8676-390d17be61b4" />
<img width="1365" height="577" alt="Dashboard" src="https://github.com/user-attachments/assets/4182cbdc-e645-4b30-9669-96440311e2f2" />
<img width="1363" height="591" alt="document" src="https://github.com/user-attachments/assets/1ee6b9dc-4a5c-4ef5-82fb-bd530c7875cd" />
<img width="1365" height="601" alt="evaluation" src="https://github.com/user-attachments/assets/296e2ff0-6a8f-497d-b32c-cd1145c0d7e4" />
<img width="1364" height="592" alt="monitoring" src="https://github.com/user-attachments/assets/49f03ac2-fa61-437a-af89-9c456d3c854d" />

<div align="center">
  <strong>Built by</strong> <a href="https://github.com/mayumarwade899">Mayur</a>
  <br/>
  <em>Portfolio project showcasing production-grade RAG system design</em>
</div>
