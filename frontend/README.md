# DocuMind Frontend

Production-grade React frontend for the DocuMind RAG system.

## Stack

- **React 18** + **Vite** — fast build tooling
- **TailwindCSS v3** — utility-first styling with dark mode
- **Zustand** — lightweight global state (chat history, UI)
- **TanStack Query v5** — server state, caching, mutations
- **Framer Motion** — production animations
- **Recharts** — composable charts
- **react-dropzone** — accessible file upload
- **react-markdown + remark-gfm** — safe markdown rendering
- **react-syntax-highlighter** — code blocks in answers
- **Native fetch** — no axios, zero supply-chain risk

## Quick start

```bash
cp .env.example .env
# edit VITE_API_URL to point at your FastAPI backend

npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Pages

| Route | Description |
|---|---|
| `/dashboard` | System overview — metrics, quick actions, recent chats |
| `/chat` | Full RAG chat with citations, debug panel, feedback |
| `/documents` | Drag-and-drop ingestion, ingest status |
| `/evaluation` | RAGAS scores, golden dataset management |
| `/monitoring` | Latency/cost charts, feedback analytics |

## Build & deploy

```bash
npm run build       # outputs to dist/

# Docker
docker build -t documind-frontend .
docker run -p 80:80 documind-frontend
```

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | FastAPI backend base URL |

## Notes

- All API calls use native `fetch` — no axios dependency
- Chat history is persisted to `localStorage` via Zustand `persist`
- Dark/light mode toggle persisted per user
- SSE streaming supported — falls back to REST if `/query/stream` not available
- Debug panel shows retrieval methods, chunk scores, verification results per message
