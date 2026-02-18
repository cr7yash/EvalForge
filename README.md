# EvalForge

**A full-stack platform for evaluating LLM outputs across accuracy, performance, and cost — built with FastAPI, Next.js, and industry-standard NLP metrics.**

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-blue?logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What It Does

EvalForge lets you run standardized evaluations against OpenAI and Anthropic models, computing **13 metrics across 3 dimensions** with a single API call:

| Dimension | Metrics |
|-----------|---------|
| **Accuracy** | Exact match, Semantic similarity (sentence embeddings), BLEU, ROUGE-L, F1 |
| **Performance** | Mean latency, P50 / P95 / P99 latency, Tokens per second |
| **Cost** | Total cost (USD), Cost per 1K tokens, Cost per example |

Results are stored in a SQLite database and displayed in a dashboard built with Next.js, Tailwind CSS, and shadcn/ui.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│              Next.js Frontend (TypeScript)           │
│   Dashboard · Eval Builder · Results · Datasets      │
└────────────────────────┬────────────────────────────┘
                         │  REST API
┌────────────────────────▼────────────────────────────┐
│               FastAPI Backend (Python)               │
│   Providers · Evaluators · Services · Routes         │
└────────┬───────────────┬────────────────────────────┘
         │               │
    ┌────▼────┐    ┌─────▼─────┐
    │ OpenAI  │    │ Anthropic │    ← LLM Providers
    │ GPT-4o  │    │ Claude    │
    └─────────┘    └───────────┘
```

### Key Design Decisions

- **Pluggable providers** — Abstract `LLMProvider` base class; adding a new provider is one file
- **Independent evaluators** — Each metric dimension (accuracy, performance, cost) runs in isolation via `BaseEvaluator`
- **Async throughout** — All LLM calls use async clients for concurrent evaluation
- **Type-safe end-to-end** — Pydantic models on backend, TypeScript interfaces on frontend

---

## Quick Start

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| API key | — | [OpenAI](https://platform.openai.com/api-keys) and/or [Anthropic](https://console.anthropic.com/) |

### 1. Clone and configure

```bash
git clone https://github.com/<your-username>/evalforge.git
cd evalforge
```

```bash
# Backend environment
cp backend/.env.example backend/.env
# Edit backend/.env and add your API key(s):
#   OPENAI_API_KEY=sk-...
#   ANTHROPIC_API_KEY=sk-ant-...
```

```bash
# Frontend environment
cp frontend/.env.example frontend/.env.local
```

### 2. Start the backend

```bash
cd backend
uv sync          # install Python dependencies
uv run uvicorn src.api.main:app --reload --port 8000
```

The API is now live at **http://localhost:8000** (interactive docs at `/docs`).

> On first run, `sentence-transformers` downloads the `all-MiniLM-L6-v2` embedding model (~80 MB). This only happens once.

### 3. Start the frontend

```bash
cd frontend
npm install      # install Node dependencies
npm run dev
```

Open **http://localhost:3000** in your browser.

---

## Usage

### Running an Evaluation

1. Navigate to **Evaluations > New Evaluation**
2. Pick a provider and model (e.g. OpenAI / `gpt-4o-mini`)
3. Add test examples with prompts and expected outputs
4. Select evaluators (Accuracy, Performance, Cost)
5. Click **Start Evaluation** — results appear in seconds

### Example payload (API)

```bash
curl -X POST http://localhost:8000/api/v1/evaluations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GPT-4o Mini Accuracy Test",
    "provider": "openai",
    "model": "gpt-4o-mini",
    "evaluators": ["accuracy", "performance", "cost"],
    "examples": [
      {"prompt": "What is the capital of France?", "expected_output": "Paris"},
      {"prompt": "Translate hello to Spanish", "expected_output": "hola"}
    ]
  }'
```

### API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/evaluations` | Create and run an evaluation |
| `GET` | `/api/v1/evaluations` | List all evaluations |
| `GET` | `/api/v1/evaluations/{id}` | Get evaluation results |
| `DELETE` | `/api/v1/evaluations/{id}` | Delete an evaluation |
| `GET` | `/api/v1/providers` | List available providers/models |
| `GET` | `/api/v1/providers/evaluators` | List available evaluators |
| `GET` | `/health` | Health check |

---

## Project Structure

```
evalforge/
├── backend/
│   ├── src/
│   │   ├── providers/          # LLM provider abstraction
│   │   │   ├── base.py         #   Abstract LLMProvider + GenerationResult
│   │   │   ├── openai_provider.py
│   │   │   └── anthropic_provider.py
│   │   ├── evaluators/         # Metric computation
│   │   │   ├── base.py         #   Abstract BaseEvaluator + EvalExample
│   │   │   ├── accuracy.py     #   BLEU, ROUGE, semantic similarity, F1
│   │   │   ├── performance.py  #   Latency percentiles, throughput
│   │   │   └── cost.py         #   Token cost analysis
│   │   ├── services/           # Orchestration
│   │   │   └── eval_service.py #   Runs providers → evaluators pipeline
│   │   ├── models/             # SQLAlchemy ORM + Pydantic schemas
│   │   ├── api/                # FastAPI routes + CORS
│   │   └── core/               # Config + database setup
│   ├── pyproject.toml
│   └── .env.example
├── frontend/
│   ├── app/                    # Next.js App Router pages
│   │   ├── page.tsx            #   Dashboard
│   │   ├── evaluations/        #   List, create, detail views
│   │   └── datasets/           #   Dataset management (planned)
│   ├── components/             # React components (shadcn/ui)
│   ├── lib/                    # API client (Axios)
│   ├── types/                  # TypeScript interfaces
│   └── package.json
├── .gitignore
├── LICENSE
└── README.md
```

---

## Metrics Reference

### Accuracy

| Metric | Range | Description |
|--------|-------|-------------|
| Exact Match | 0–1 | Binary: does the response exactly match the expected output? |
| Semantic Similarity | 0–1 | Cosine similarity of sentence embeddings (`all-MiniLM-L6-v2`) |
| BLEU | 0–1 | N-gram overlap score (standard MT metric) |
| ROUGE-L | 0–1 | Longest common subsequence F-measure |
| F1 | 0–1 | Token-level precision × recall harmonic mean |

### Performance

| Metric | Unit | Description |
|--------|------|-------------|
| Mean Latency | ms | Average response time |
| P50 / P95 / P99 | ms | Percentile latencies for tail-latency analysis |
| Tokens/sec | tok/s | Output token generation throughput |

### Cost

| Metric | Unit | Description |
|--------|------|-------------|
| Total Cost | USD | Sum of input + output token costs |
| Cost per 1K Tokens | USD | Normalized cost metric for comparison |
| Cost per Example | USD | Average cost per test case |

---

## Supported Models

| Provider | Models | Pricing (per 1K tokens) |
|----------|--------|------------------------|
| **OpenAI** | gpt-4o, gpt-4o-mini, gpt-4-turbo | $0.005–$0.03 output |
| **Anthropic** | claude-sonnet-4, claude-3.5-sonnet, claude-3.5-haiku | $0.004–$0.015 output |

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLAlchemy, Pydantic, uvicorn |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| NLP | sentence-transformers, NLTK (BLEU), rouge-score, scikit-learn |
| LLM SDKs | openai, anthropic |
| HTTP | Axios (frontend), httpx (backend) |

---

## Troubleshooting

**Backend won't start — "No module named 'src'"**
Make sure you're in the `backend/` directory and using `uv run`.

**"API key not found"**
Check that `backend/.env` exists and contains at least one valid key without quotes.

**Frontend can't reach backend**
Verify the backend is running on port 8000 and `frontend/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`.

**Low exact-match scores**
This is expected — LLMs rarely produce character-for-character matches. Focus on `semantic_similarity` for a more meaningful accuracy signal.

**Slow first evaluation**
The first run downloads the sentence-transformer model (~80 MB). Subsequent runs use the cached model.

---

## License

[MIT](LICENSE)
