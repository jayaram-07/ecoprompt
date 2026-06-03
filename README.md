# EcoPrompt — Energy-Efficient AI Prompt Routing

> A hierarchical router that answers each prompt with the **cheapest, lowest-energy engine that can do the job** — sending trivial queries to deterministic/local handlers and reserving large LLMs only for prompts that genuinely need them. The result: lower latency, lower cost, and less compute/carbon per query.

Most apps send *every* prompt to a large model, even "what is the capital of France?" EcoPrompt asks a different question first: **what is the smallest engine that can answer this correctly?** — then routes accordingly, and measures the energy and cost it saved.

![EcoPrompt architecture](diagrams/ecoprompt_architecture.png)

## How it works

Each incoming prompt is scored for complexity and pushed through a cascade of routes, cheapest first. It only escalates to a paid LLM when the cheaper tiers can't answer confidently.

| Tier | Route | Engine | Cost / Energy |
|------|-------|--------|---------------|
| 1 | `deterministic` | Rule/lookup engine (math, geography, exact facts) | ~0 |
| 2 | `kb_reasoned_local` / `rag_local` | Local knowledge base + lightweight RAG retrieval | ~0 |
| 3 | `template_engine` | Code-template responder for common programming asks | ~0 |
| 4 | `local` | Groq **Llama 3.1 8B Instant** (small, fast) | low |
| 5 | `groq` | Groq **Llama 3 70B** (heavier reasoning) | higher |
| 6 | `web` | **Gemini** grounded web search (fresh / real-time facts) | highest |

A response from a cheaper tier is sanity-checked (entity coverage, weak-answer and truncation detection); if it looks weak, EcoPrompt escalates to the next tier instead of returning a bad answer.

### Built-in knowledge base
The local tiers are backed by curated KB modules under [`kb/`](kb/) — geography, math, science (physics / chemistry / biology), history, programming, and high-level concepts — plus a small RAG engine (`rag_engine.py`) for semantic lookup. These answer a large share of everyday prompts with **zero LLM calls.**

### Energy & cost accounting
Every request records latency, estimated energy (kWh), and estimated cost per route, exposed at `/metrics` and visualized in the dashboard. Baselines used for comparison:
- GPT-4o: ~$4.00 / 1M tokens
- Groq Llama 3 70B: ~$0.70 / 1M tokens
- Electricity: ₹8.00 / kWh (India avg)

## Tech stack

**Backend** — Python, FastAPI, Uvicorn · [Groq](https://groq.com) (Llama 3.1 8B / Llama 3 70B) · Google Gemini (grounded search) · custom deterministic + RAG engines
**Frontend** — React + Vite + Tailwind CSS · Recharts (metrics dashboard) · react-markdown + syntax highlighting · Axios

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/generate` | Route a prompt and return the answer + chosen route |
| `POST` | `/generate-stream` | Same, streamed token-by-token |
| `GET`  | `/metrics` | Aggregate latency / energy / cost per route |

## Running locally

### 1. Backend
```bash
pip install -r requirements.txt
cp .env.example .env          # then fill in your keys
uvicorn main:app --reload
```
Backend runs at `http://localhost:8000`.

### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
Frontend runs at `http://localhost:5173`.

### Environment variables
See [`.env.example`](.env.example). You'll need:
- `GROQ_API_KEY` — from [console.groq.com](https://console.groq.com) (powers the local/large LLM tiers)
- `GEMINI_API_KEY` — from [Google AI Studio](https://aistudio.google.com) (powers the grounded web-search tier)

## Project layout
```
main.py              FastAPI app — routing cascade, metrics, streaming
deterministic.py     Tier-1 rule/lookup engine
kb/                  Knowledge-base lookups + RAG engine (geography, math, science, …)
diagrams/            Architecture diagrams (.png/.svg/.mmd)
frontend/            Vite + React + Tailwind UI and metrics dashboard
```

## Roadmap
- Pluggable model backends beyond Groq/Gemini
- Configurable routing policy / thresholds
- Per-user energy & cost reports

---
*Built by [K Jayarama Das](https://github.com/jayaram-07).*
