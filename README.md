# EvalForge

**A full-stack platform for evaluating LLM outputs across accuracy, performance, and cost — built with FastAPI, Next.js, and industry-standard NLP metrics.**

![Python](https://img.shields.io/badge/Python-3.12+-blue?logo=python&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-blue?logo=typescript&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.128-009688?logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-black?logo=next.js&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-green)

---

## What It Does

EvalForge lets you run standardized evaluations against **46 models** from OpenAI, Anthropic, Google, Mistral and others — all reached through a single [Portkey](https://portkey.ai) gateway key — computing **18 metrics across 3 dimensions** with a single API call:

| Dimension | Metrics |
|-----------|---------|
| **Accuracy** | Exact match, Semantic similarity (sentence embeddings), BLEU, ROUGE-L, F1 |
| **Performance** | Mean latency, 3 latency percentiles (P50 / P95 / P99), Tokens per second |
| **Cost** | Total / input / output cost (USD), Cost per 1K tokens, Cost per example, Input / output / total tokens |

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
         ┌────────▼─────────┐
         │  Portkey Gateway  │        ← one key, OpenAI-compatible
         └────────┬─────────┘
    ┌─────────┬───┴────┬──────────┐
    │ OpenAI  │ Claude │ Gemini · │    ← vendor families
    │ GPT-5.x │ Opus 5 │ Mistral  │
    └─────────┴────────┴──────────┘
```

### Key Design Decisions

- **One gateway, many vendors** — Portkey speaks the OpenAI protocol for every upstream provider, so a single client covers all of them
- **Per-model request shaping** — Parameter support is not uniform across models (reasoning models reject `max_tokens`, `temperature` and `stop`), so each model declares its capabilities in `portkey_catalog.py` and requests are built to match
- **Pluggable providers** — Abstract `LLMProvider` base class; direct OpenAI/Anthropic access remains available as a fallback
- **Independent evaluators** — Each metric dimension (accuracy, performance, cost) runs in isolation via `BaseEvaluator`
- **Concurrent generation** — Examples are generated in parallel via `asyncio.gather`, bounded by a semaphore (`MAX_CONCURRENT_REQUESTS`, default 8) so large datasets don't trip provider rate limits. Results stay aligned to their examples regardless of completion order
- **Type-safe end-to-end** — Pydantic models on backend, TypeScript interfaces on frontend

---

## Quick Start

### Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| Node.js | 18+ | [nodejs.org](https://nodejs.org/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| API key | — | [Portkey](https://portkey.ai) (one key covers every model) |

### 1. Clone and configure

```bash
git clone https://github.com/cr7yash/EvalForge.git
cd EvalForge
```

```bash
# Backend environment
cp backend/.env.example backend/.env
# Edit backend/.env and add your gateway key:
#   PORTKEY_API_KEY=...
#
# Optional — tune generation concurrency (default 8):
#   MAX_CONCURRENT_REQUESTS=8
#
# Optional — only to bypass the gateway and call a vendor directly:
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
2. Pick a provider and model (e.g. OpenAI / `gpt-5.5`, or Anthropic / `claude-opus-5`)
3. Add test examples with prompts and expected outputs
4. Select evaluators (Accuracy, Performance, Cost)
5. Click **Start Evaluation** — results appear in seconds

### Example payload (API)

```bash
curl -X POST http://localhost:8000/api/v1/evaluations \
  -H "Content-Type: application/json" \
  -d '{
    "name": "GPT-5.5 Accuracy Test",
    "provider": "openai",
    "model": "gpt-5.5",
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
│   │   │   ├── portkey_catalog.py  # Model catalog + per-model param support
│   │   │   ├── portkey_provider.py # Gateway provider (primary)
│   │   │   ├── openai_provider.py  # Direct access (optional fallback)
│   │   │   └── anthropic_provider.py
│   │   ├── evaluators/         # Metric computation
│   │   │   ├── base.py         #   Abstract BaseEvaluator + EvalExample
│   │   │   ├── accuracy.py     #   BLEU, ROUGE, semantic similarity, F1
│   │   │   ├── performance.py  #   Latency percentiles, throughput
│   │   │   └── cost.py         #   Token cost analysis
│   │   ├── services/           # Orchestration
│   │   │   └── eval_service.py #   Concurrent generation → evaluators pipeline
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

46 models are reachable through the Portkey gateway, grouped by vendor family.
`GET /api/v1/providers` returns the live list.

| Family | Count | Examples |
|--------|-------|----------|
| **OpenAI** | 19 | `gpt-5.5`, `gpt-5.6-sol`, `gpt-4.1`, `gpt-4o-mini`, `o4-mini` |
| **Anthropic** | 10 | `claude-opus-5`, `claude-sonnet-5`, `claude-opus-4-8`, `claude-haiku-4-5` |
| **Google** | 11 | `gemini-3.7-flash`, `gemini-2.5-pro`, `gemma-4-31b` |
| **Mistral** | 3 | `mistral-large-3`, `mixtral-8x7b` |
| **Other** | 3 | `deepseek-r1`, `kimi-k2.5` |

**Pricing** is recorded for the mainstream models only. Where a public list
price is not known, the Cost evaluator reports `pricing_known: false` and its
dollar figures should be ignored — token counts remain accurate.

**Reasoning models** (`gpt-5.x`, `o3`/`o4`, `gemini-3.x`, `deepseek-r1`) spend
their output budget on hidden reasoning before writing an answer. EvalForge
raises the token budget to a safe floor for these models automatically; any
response that still comes back empty or truncated is flagged on the
evaluation rather than silently scored as a zero.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLAlchemy, Pydantic, uvicorn |
| Frontend | Next.js 15, React 19, TypeScript, Tailwind CSS, shadcn/ui |
| NLP | sentence-transformers, NLTK (BLEU), rouge-score, scikit-learn |
| LLM access | Portkey AI gateway (via the `openai` SDK); `anthropic` for direct fallback |
| HTTP | Axios (frontend), httpx (backend) |

---

## Troubleshooting

**Backend won't start — "No module named 'src'"**
Make sure you're in the `backend/` directory and using `uv run`.

**"API key not found" / no providers listed**
Check that `backend/.env` exists and contains `PORTKEY_API_KEY` without quotes.
`GET /api/v1/providers` returns an empty list when no key is configured.

**"no such column: ..." after pulling new changes**
Restart the backend. New nullable columns and new tables are applied to your
existing database automatically on startup, preserving stored evaluations —
there is no need to delete `backend/evalforge.db`.

**Rate limit errors (429) on large datasets**
Lower `MAX_CONCURRENT_REQUESTS` in `backend/.env`; it defaults to 8 in-flight
requests.

**A model returns empty responses**
Reasoning models can exhaust the output budget before emitting text. Raise
`max_tokens` in the evaluation config, or lower `reasoning_effort`.

**Frontend can't reach backend**
Verify the backend is running on port 8000 and `frontend/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1`.

**Low exact-match scores**
This is expected — LLMs rarely produce character-for-character matches. Focus on `semantic_similarity` for a more meaningful accuracy signal.

**Slow first evaluation**
The first run downloads the sentence-transformer model (~80 MB). Subsequent runs use the cached model.

---

## License

[MIT](LICENSE)
