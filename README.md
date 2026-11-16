---
title: RAG CI Quality Gate Studio
emoji: 🛡️
colorFrom: purple
colorTo: indigo
sdk: docker
app_port: 7860
---

# RAG CI Quality Gate Studio — Yassir Benhaddouche

Welcome to the **RAG CI Quality Gate Studio**, an enterprise-grade evaluation console and CI regression gate designed for production Retrieval-Augmented Generation (RAG) systems. Built with FastAPI, React + TypeScript, Vite, Tailwind CSS, and DeepEval/Ragas.

---

## Problem & Architecture

RAG applications regress silently. A prompt change, document update, or embedding shift can quietly break recall or introduce hallucinations while average dashboard metrics mask the failure. 

This studio decouples evaluation into two distinct halves of the pipeline:
1. **Retrieval Health** (`Context Precision` + `Context Recall`): Evaluates whether the retriever surfaces the exact supporting knowledge base chunks without crowding the context window with noise.
2. **Generation Health** (`Faithfulness` + `Answer Relevancy`): Evaluates whether the LLM answer is strictly grounded in the retrieved chunks and directly answers the user query.

---

## Statistical Gating (4/5 Runs)

LLM judges are inherently non-deterministic. Traditional single-run evaluation gates produce flaky CI pipelines that developers quickly disable. 

The RAG CI Gate solves this by running the evaluation suite across **5 repeated runs (`GATE_RUNS=5`)** and requiring each metric to clear its threshold in at least **4 of them (`REQUIRED_PASSING_RUNS=4`)**. A question or prompt regression that drifts from 5/5 to 2/5 is caught immediately without false positives caused by judge variance.

---

## Three Testing Tiers

1. **Zero-Cost Interactive CI Gate**: Powered by `backend/demo_snapshots.json` and real-time threshold sliders across 4 engineering presets (`Healthy baseline`, `Broken retriever`, `Hallucinating prompt`, etc.). Test threshold adjustments instantly with zero API calls.
2. **Zero-Key Deterministic Retrieval Sandbox**: Test custom queries against `POST /api/evaluate/retrieval-check` running `rag_pipeline.py` against `corpus/chunks.jsonl` with zero API key required, displaying similarity scores, chunk text, and ground-truth hit/noise badges.
3. **Live BYOK Evaluation & GitHub Actions Gate**: Execute live test cases through `POST /api/evaluate/live` supporting both OpenAI (`sk-...`) and native Groq (`gsk_...`) API keys (automatically routing Groq keys to `https://api.groq.com/openai/v1` with model `openai/gpt-oss-120b`). Includes the drop-in GitHub Actions CI workflow at `.github/workflows/rag-eval-gate.yml`.

---

## Project Structure

```text
rag-evaluation-metrics/
├── backend/
│   ├── __init__.py
│   ├── demo_snapshots.json
│   └── main.py              # FastAPI backend & API endpoints
├── frontend/                # React + TS + Vite + Tailwind CSS console
│   ├── src/
│   ├── package.json
│   └── vite.config.ts
├── corpus/
│   └── chunks.jsonl         # Knowledge base chunks
├── benchmark/
│   └── rag_benchmark_v3.jsonl # Versioned benchmark dataset
├── tests/
│   └── test_rag_gate.py     # pytest regression gate
├── scripts/
│   ├── extract_questions.py # Mine questions from chat logs
│   └── generate_snapshots.py
├── Dockerfile               # Multi-stage production Dockerfile
└── requirements.txt         # Python dependencies
```

---

## Local Quickstart & Pytest Commands

### Prerequisites
- Python 3.10+
- Node.js 18+

### Linux / macOS

```bash
# 1. Clone & setup Python environment
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Build frontend
cd frontend
npm install
npm run build
cd ..

# 3. Run FastAPI backend (serves API & React UI on port 7860)
uvicorn backend.main:app --host 0.0.0.0 --port 7860
```

### Windows (PowerShell 5.1+)

```powershell
# 1. Setup Python environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 2. Build frontend
cd frontend
npm install
npm run build
cd ..

# 3. Run FastAPI backend
uvicorn backend.main:app --host 0.0.0.0 --port 7860
```

### Running Tests & CI Gate

```powershell
# Run retrieval sanity check (Zero API cost)
pytest tests/test_rag_gate.py::test_retrieval_hits_ground_truth_chunks -v

# Run full CI gate with OpenAI key
export OPENAI_API_KEY="sk-..."
pytest tests/test_rag_gate.py -v
```

---

## License

Released under the [MIT License](./LICENSE), copyright 2026 Yassir Benhaddouche & Autonoma Labs.
