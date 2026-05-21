<div align="center">

# 🔬 ResearchKit AI

### The private, self-hosted research intelligence platform for ML PhD students entering industry

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC143C)](https://qdrant.tech)
[![Groq](https://img.shields.io/badge/Groq-LLaMA_3.3_70B-F55036)](https://groq.com)
[![Chrome](https://img.shields.io/badge/Chrome-Extension_MV3-4285F4?logo=googlechrome&logoColor=white)](https://developer.chrome.com/docs/extensions)
[![Tests](https://img.shields.io/badge/Tests-33_passing-brightgreen?logo=pytest)](backend/tests/)
[![License](https://img.shields.io/badge/License-MIT-22c55e)](LICENSE)

**Built by [Mahboob Alam](https://github.com/MahboobAlam0) · M.Tech Data Science · DIAT-DU Pune**

[Features](#-features) · [Architecture](#-architecture) · [Quickstart](#-quickstart) · [API Reference](#-api-reference) · [Running Tests](#-running-tests)

</div>

---

## Who It's For & Why It Exists

**Target user: ML/DS PhD students and researchers entering industry.**

They are doing two things simultaneously — conducting research and job-hunting. No single tool serves both. More importantly, existing research tools have a critical flaw: **they send your unpublished work to their servers.**

| Tool | What it does | Why it falls short |
|------|-------------|-------------------|
| Zotero / Mendeley | Paper storage | Zero AI — can't ask questions across your library |
| Elicit / Consensus | AI over the web | Cloud-only, sends your papers to their servers, subscription |
| ChatPDF | Chat with a PDF | One paper at a time, no cross-library synthesis |
| Semantic Scholar | Paper discovery | No personal library, no Q&A |
| Perplexity | General AI search | Not grounded in your specific saved papers |

**ResearchKit is the only tool that:**
1. **Runs on your own infrastructure** — your unpublished research never leaves your machine (or your private cloud)
2. **Imports your existing Zotero library in one click** (BibTeX) — zero re-entry
3. **Auto-tags every paper** with task, methods, datasets, and key result — making your library a structured research database, not just a pile of PDFs
4. **Ranks new arXiv papers by relevance to YOUR library** — using what you've already read as an implicit interest profile
5. **Generates cited literature syntheses** with contradiction detection and research gap identification
6. **Analyzes skill gaps** against job descriptions using the same embedding pipeline — because the same person needs both features

---

## ✨ Features

### 📚 Import Your Entire Zotero / Mendeley Library in One Click
Export your existing reference manager as a `.bib` file. ResearchKit parses it, chunks every paper, embeds it, and indexes it — your full research history becomes queryable in seconds. Works with any BibTeX export.

### 🏷 AI Auto-Tagging on Every Save
Every paper ingested (web scrape, PDF, or BibTeX) is automatically tagged by the LLM with:
- **Task** — the research problem (e.g. "long-context reasoning")
- **Methods** — key techniques (e.g. "RoPE", "flash attention", "LoRA")
- **Datasets** — benchmarks used (e.g. "MMLU", "HumanEval")
- **Key result** — the most important finding in one sentence

Tags appear on paper cards and make your library a structured research database — not just a pile of saved links.

### 💬 RAG Chat over Your Private Library
Ask natural-language questions across your entire paper collection. Answers are grounded in your specific papers with inline `[1]`, `[2]` citations — no hallucination, no generic web answers.

### 📄 Full PDF Upload & Indexing
Upload any PDF — including papers behind paywalls or unpublished preprints. Full text is extracted with PyMuPDF (not just the abstract), chunked with overlap, and embedded for deep retrieval.

### 🔭 Literature Synthesis + Contradiction Detection + Research Gaps
Given a research question, ResearchKit retrieves the top-k chunks and generates — in a single LLM call — a cited synthesis paragraph, specific contradictions between papers, and concrete research gaps. Draft a literature review section in seconds instead of days.

### 📡 ArXiv Digest Ranked by YOUR Library
Your saved papers act as an implicit interest profile. ResearchKit fetches today's arXiv papers, embeds each abstract, and ranks them by cosine similarity to your library. You see papers you'd actually care about — no noise, no keyword tuning.

### 🎯 JD Skill-Gap Analyzer
The same embedding pipeline that powers paper retrieval also powers career intelligence. Paste a JD and your resume — the LLM extracts skills from both, semantic matching surfaces gaps, and a 4-step action plan tells you exactly what to learn next.

### 🌐 Dual Interface — Extension + Web
- **Chrome Extension** (MV3) — one-click save from arXiv, PubMed, Semantic Scholar
- **Web Frontend** — full-page dashboard at `localhost:3000` or GitHub Pages

---

## 🏗 Architecture

```
┌────────────────────────────────────────────────────────────────────┐
│  Interfaces                                                        │
│  ┌─────────────────────┐        ┌──────────────────────────────┐  │
│  │   Chrome Extension  │        │   Web Frontend (port 3000)   │  │
│  │   (MV3 · Popup UI)  │        │   (nginx · Vanilla JS/CSS)   │  │
│  └──────────┬──────────┘        └──────────────┬───────────────┘  │
└─────────────│─────────────────────────────────│───────────────────┘
              │  HTTP/REST                       │
              ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│  FastAPI Backend  (port 8000)                                       │
│                                                                     │
│  POST /api/papers/ingest       ──► embed + store scraped paper      │
│  POST /api/papers/upload-pdf   ──► PyMuPDF extract + full index     │
│  GET  /api/papers/search       ──► semantic search  (no LLM)        │
│  POST /api/papers/synthesize   ──► synthesis + contradictions + gaps│
│  POST /api/chat/query          ──► RAG Q&A with citations           │
│  POST /api/digest/fetch        ──► arXiv digest ranked by library   │
│  POST /api/jd/analyze          ──► skill-gap analysis               │
│  GET  /api/stats               ──► library stats + system info      │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Embedding Service  ·  BAAI/bge-base-en-v1.5  (768-dim)     │  │
│  │  BGE retrieval instruction prefix on queries (asymmetric)    │  │
│  └─────────────────────────────┬────────────────────────────────┘  │
│                                │                                    │
│  ┌─────────────────────────────▼────────────────────────────────┐  │
│  │  Qdrant Vector DB  ·  cosine similarity  ·  payload indexes  │  │
│  │  Local Docker  or  Qdrant Cloud                              │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                     │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │  Groq LLM  ·  llama-3.3-70b-versatile                       │  │
│  │  RAG answers · skill extraction · synthesis · action plans   │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🛠 Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Backend** | FastAPI 0.115 · Python 3.11 · async/await | High-performance async API |
| **Embeddings** | `BAAI/bge-base-en-v1.5` (768-dim) | Top MTEB retrieval score; asymmetric query/doc encoding |
| **Vector DB** | Qdrant (Docker + Cloud) | Payload indexes, cosine similarity, async client |
| **LLM** | Groq · `llama-3.3-70b-versatile` | Fast inference, free tier, JSON-structured outputs |
| **PDF Parsing** | PyMuPDF | Fast, noise-aware text extraction with section detection |
| **Extension** | Chrome MV3 · Vanilla JS | No build step; content scripts on 3 academic sites |
| **Web UI** | nginx · Vanilla JS/CSS | Zero dependencies; drag-and-drop deploy to Netlify |
| **Deployment** | Docker Compose · Railway | `railway.toml` included; single-command cloud deploy |
| **Testing** | pytest · pytest-asyncio | 33 tests; all I/O mocked — runs without Docker or API keys |

---

## 🚀 Quickstart

### Prerequisites
- Docker Desktop
- A free [Groq API key](https://console.groq.com/) (for LLM)
- *(Optional)* A free [Qdrant Cloud](https://cloud.qdrant.io/) cluster (for persistent cloud storage)

### 1 — Clone & configure

```bash
git clone https://github.com/MahboobAlam0/research-toolkit.git
cd research-toolkit

cp .env.example .env
# Edit .env — add GROQ_API_KEY (and optionally QDRANT_URL + QDRANT_API_KEY)
```

### 2 — Start the backend

```bash
docker compose up --build backend
# FastAPI → http://localhost:8000
# Swagger  → http://localhost:8000/docs
```

First run downloads `BAAI/bge-base-en-v1.5` (~438 MB) into the image. Subsequent starts take ~10 s.

### 3 — Start the web frontend

```bash
docker compose up frontend -d
# Web UI → http://localhost:3000
```

### 4 — Load the Chrome extension *(optional)*

1. `chrome://extensions/` → enable **Developer mode**
2. **Load unpacked** → select the `extension/` folder
3. Pin the ResearchKit AI icon

---

## 📖 Usage

### Save papers & chat

Visit any arXiv/PubMed/Semantic Scholar paper → click **Save to ResearchKit**.  
Open the extension or web UI → **Chat** tab → ask questions about your library.

```
Q: How do transformers handle positional encoding?
A: According to [1] Vaswani et al. (2017), the original Transformer uses sinusoidal
   positional encodings… [2] Su et al. (2023) propose RoPE as an alternative…
```

### Synthesize literature

```
Research question: "What are the limitations of RLHF for aligning LLMs?"

→ Synthesis:   Papers [1,3] identify reward hacking as a core failure mode…
→ Contradictions: [2] reports RLHF improves honesty by 40%; [5] finds marginal gains…  
→ Gaps:        No paper evaluates RLHF under adversarial prompt injection at scale.
```

### ArXiv digest

Add interests → `diffusion models`, `RAG`, `code generation`  
Click **Check New Papers** → ranked list of today's arXiv papers by relevance to your library.

### JD Analyzer

Paste a job description + your resume → get a **match score**, **missing skills**, and a **4-step action plan**.

---

## 📂 Project Structure

```
research-toolkit/
│
├── backend/                        # FastAPI application
│   ├── main.py                     # App entrypoint + /api/stats
│   ├── routes/
│   │   ├── ingest.py               # Paper CRUD + payload index setup
│   │   ├── pdf_upload.py           # Full-text PDF ingestion
│   │   ├── search.py               # Fast semantic search (no LLM)
│   │   ├── synthesize.py           # Literature synthesis + gap detection
│   │   ├── query.py                # RAG chat with citations
│   │   ├── digest.py               # arXiv digest ranked by library relevance
│   │   └── jd_analyzer.py          # Skill-gap analysis
│   ├── services/
│   │   ├── embedder.py             # BGE singleton + query instruction prefix
│   │   ├── rag_pipeline.py         # Retrieve + Qdrant Cloud support
│   │   ├── llm_client.py           # Groq async wrapper
│   │   ├── pdf_extractor.py        # PyMuPDF noise-aware extraction
│   │   └── arxiv_client.py         # arXiv Atom API async client
│   ├── models/schemas.py           # Pydantic v2 models with field validation
│   ├── tests/                      # 33 pytest tests (all I/O mocked)
│   │   ├── conftest.py             # Fixtures — no Docker/API keys needed
│   │   ├── test_chunking.py        # 6 pure unit tests
│   │   ├── test_jd.py              # 9 JD analyzer tests
│   │   └── test_api.py             # 18 route integration tests
│   ├── requirements.txt
│   └── Dockerfile                  # CPU-only torch; pre-bakes BGE model
│
├── extension/                      # Chrome Extension (MV3)
│   ├── manifest.json               # optional_host_permissions for custom backends
│   ├── popup.html / popup.js       # 4-tab UI: Papers · Chat · Digest · JD
│   ├── options.html / options.js   # Configurable backend URL + permission request
│   ├── js/content.js               # Page scraper (arXiv · PubMed · Semantic Scholar)
│   └── js/background.js            # Badge updates
│
├── frontend/                       # Web UI (nginx on port 3000)
│   ├── index.html                  # Full-page layout with sidebar navigation
│   ├── css/style.css               # Dark theme, CSS variables, responsive grid
│   └── js/app.js                   # All feature logic — no framework dependencies
│
├── docker-compose.yml              # Backend + Frontend + Qdrant (local)
├── railway.toml                    # One-command Railway cloud deploy
├── build-extension.ps1             # Package extension as .zip for Chrome Web Store
└── .env.example                    # Environment variable template
```

---

## 🔌 API Reference

Full interactive docs at **http://localhost:8000/docs**

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Liveness check |
| `GET` | `/api/stats` | Paper count, source breakdown, model info |
| `POST` | `/api/papers/ingest` | Embed + store a scraped paper |
| `POST` | `/api/papers/upload-pdf` | Upload and index a full PDF (25 MB max) |
| `GET` | `/api/papers/list` | All saved papers (metadata) |
| `GET` | `/api/papers/search?q=…` | Fast semantic search — no LLM, ~50 ms |
| `GET` | `/api/papers/count` | O(1) paper count via Qdrant native counter |
| `DELETE` | `/api/papers/{id}` | Delete paper and all its chunks |
| `POST` | `/api/papers/synthesize` | Literature synthesis + contradictions + gaps |
| `POST` | `/api/chat/query` | RAG Q&A with cited sources + conversation history |
| `POST` | `/api/digest/fetch` | arXiv papers ranked by library relevance |
| `POST` | `/api/jd/analyze` | Skill-gap analysis against a job description |

---

## ✅ Running Tests

No Docker, no API keys, no GPU — all external I/O is mocked.

```bash
cd backend
pip install -r requirements.txt
pytest tests/ -v
```

```
tests/test_chunking.py  ......          6 passed
tests/test_jd.py        .........       9 passed
tests/test_api.py       ..................  18 passed
━━━━━━━━━━━━━━━━━━━━━━━━━━━━
33 passed in ~4s
```

---

## ☁️ Deploying to Production

### Backend → Railway (no GitHub required)

```bash
npm install -g @railway/cli
railway login
railway init
railway up
```

Set environment variables in the Railway dashboard:
```
GROQ_API_KEY   = gsk_...
QDRANT_URL     = https://your-cluster.cloud.qdrant.io:6333
QDRANT_API_KEY = your_qdrant_key
```

### Frontend → Netlify Drop

Drag the `frontend/` folder to **netlify.com/drop** — done in 30 seconds, no account required.

### Chrome Web Store

```powershell
.\build-extension.ps1
# Creates researchkit-ai-v1.1.0.zip
# Upload at chrome.google.com/webstore/devconsole
```

---

## 🧠 How It Works

### RAG Pipeline

```
User query
    │
    ▼
BGE query encoder  ←── prepends retrieval instruction prefix
    │  768-dim vector
    ▼
Qdrant ANN search  ──► top-K most similar paper chunks
    │
    ▼
Prompt builder     ──► numbered context + conversation history
    │
    ▼
Groq LLM           ──► cited answer
```

### JD Skill Matching

```
JD text ──► LLM ──► [skill_1, skill_2, …]  ┐
                                             ├─► batch embed ──► cosine similarity matrix
Resume  ──► LLM ──► [skill_a, skill_b, …]  ┘                         │
                                                               threshold = 0.80
                                                                      │
                                                     matched / missing / score (0–1)
                                                                      │
                                                              LLM action plan
```

### Literature Synthesis (single LLM call)

Rather than chaining three separate LLM calls (slow, incoherent), ResearchKit sends one structured prompt requesting a JSON object with `synthesis`, `contradictions`, and `gaps` — the model has the full context for all three simultaneously.

---

## 🗺 Roadmap

- [ ] Multi-user support with JWT auth
- [ ] Citation graph visualization (D3.js)
- [ ] Hypothesis generator from research gaps
- [ ] Export literature review as Markdown / LaTeX
- [ ] Fine-tuned domain embeddings (biomedical, CS)
- [ ] Scheduled digest with push notifications

---

## 📄 License

MIT © 2025 Mahboob Alam

---

<div align="center">

**If this project helped you, consider giving it a ⭐**

Built with FastAPI · Qdrant · Groq · sentence-transformers · Chrome MV3

</div>
