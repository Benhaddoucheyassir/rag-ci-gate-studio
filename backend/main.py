"""FastAPI console backend for the four-metric RAG evaluation gate.

Endpoints:

    GET  /api/presets
    POST /api/evaluate/snapshot          recompute 5-run verdicts from stored scores
    POST /api/evaluate/retrieval-check   deterministic retrieve() vs gold chunk IDs
    POST /api/evaluate/live              one test case through the pipeline + DeepEval

When `frontend/dist` exists it is mounted at `/` so the API and the UI share a port.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

SNAPSHOT_PATH = Path(__file__).resolve().parent / "demo_snapshots.json"
BENCHMARK_PATH = ROOT / "benchmark" / "rag_benchmark_v3.jsonl"
FRONTEND_DIST = ROOT / "frontend" / "dist"

METRIC_ORDER = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


def load_snapshots() -> dict[str, Any]:
    if not SNAPSHOT_PATH.exists():
        raise FileNotFoundError(
            f"Missing {SNAPSHOT_PATH}. Run python scripts/generate_snapshots.py first."
        )
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


def load_benchmark() -> list[dict]:
    entries = []
    with BENCHMARK_PATH.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def preset_by_id(snapshots: dict[str, Any], preset_id: str) -> dict[str, Any]:
    for preset in snapshots["presets"]:
        if preset["id"] == preset_id:
            return preset
    raise HTTPException(status_code=404, detail=f"Unknown preset {preset_id!r}")


def verdict_for(
    runs: list[dict],
    thresholds: dict[str, float],
    required_passing_runs: int,
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for name in METRIC_ORDER:
        threshold = float(thresholds[name])
        scores = [float(run["scores"][name]) for run in runs]
        reasons = [run.get("reasons", {}).get(name, "") for run in runs]
        passing = [s for s in scores if s >= threshold]
        metrics[name] = {
            "threshold": threshold,
            "scores": scores,
            "reasons": reasons,
            "passing_runs": len(passing),
            "total_runs": len(scores),
            "passed": len(passing) >= required_passing_runs,
        }
    overall = all(m["passed"] for m in metrics.values())
    return {
        "verdict": "PASS" if overall else "BLOCKED",
        "required_passing_runs": required_passing_runs,
        "gate_runs": len(runs),
        "metrics": metrics,
    }


app = FastAPI(title="RAG evaluation console", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SnapshotRequest(BaseModel):
    preset_id: str = "healthy_baseline"
    thresholds: dict[str, float] | None = None
    required_passing_runs: int | None = None


class RetrievalCheckRequest(BaseModel):
    preset_id: str | None = None
    top_k: int | None = None
    noise_injection: bool | None = None
    question: str | None = None


class LiveRequest(BaseModel):
    question: str | None = None
    benchmark_id: str | None = None
    preset_id: str | None = None
    top_k: int = 3
    prompt_mode: str = "strict"
    noise_injection: bool = False
    api_key: str | None = Field(default=None, description="Optional user-supplied OpenAI key")
    thresholds: dict[str, float] | None = None


@app.get("/api/presets")
def get_presets() -> dict[str, Any]:
    snapshots = load_snapshots()
    return {
        "gate_runs": snapshots["gate_runs"],
        "required_passing_runs": snapshots["required_passing_runs"],
        "default_thresholds": snapshots["default_thresholds"],
        "metric_labels": snapshots.get("metric_labels", {}),
        "presets": [
            {
                "id": p["id"],
                "title": p["title"],
                "description": p["description"],
                "config": p["config"],
            }
            for p in snapshots["presets"]
        ],
    }


@app.post("/api/evaluate/snapshot")
def evaluate_snapshot(body: SnapshotRequest) -> dict[str, Any]:
    snapshots = load_snapshots()
    preset = preset_by_id(snapshots, body.preset_id)
    thresholds = dict(snapshots["default_thresholds"])
    if body.thresholds:
        thresholds.update({k: float(v) for k, v in body.thresholds.items() if k in thresholds})
    required = (
        snapshots["required_passing_runs"]
        if body.required_passing_runs is None
        else body.required_passing_runs
    )
    gate = verdict_for(preset["runs"], thresholds, required)
    return {
        "preset": {
            "id": preset["id"],
            "title": preset["title"],
            "description": preset["description"],
            "config": preset["config"],
        },
        **gate,
    }


def _chunk_id_of(chunk: Any) -> str | None:
    if isinstance(chunk, str):
        return chunk
    if isinstance(chunk, dict):
        return chunk.get("chunk_id")
    return getattr(chunk, "chunk_id", None)


@app.post("/api/evaluate/retrieval-check")
def evaluate_retrieval(body: RetrievalCheckRequest) -> dict[str, Any]:
    from rag_pipeline import retrieve, _score_chunks

    snapshots = load_snapshots()
    top_k = body.top_k
    noise = body.noise_injection
    if body.preset_id:
        preset = preset_by_id(snapshots, body.preset_id)
        top_k = preset["config"]["top_k"] if top_k is None else top_k
        noise = preset["config"]["noise_injection"] if noise is None else noise
    if top_k is None:
        top_k = 3
    if noise is None:
        noise = False

    benchmark = load_benchmark()
    if body.question:
        benchmark = [
            {
                "id": "ad-hoc",
                "question": body.question,
                "ground_truth_chunk_ids": [],
            }
        ]

    results = []
    misses = []
    for entry in benchmark:
        q = entry["question"]
        expected = set(entry.get("ground_truth_chunk_ids") or [])
        retrieved_chunks = retrieve(q, top_k=top_k, noise_injection=noise)
        scored_dict = {c["chunk_id"]: score for score, c in _score_chunks(q)}

        retrieved_details = []
        retrieved_ids = []
        for c in retrieved_chunks:
            cid = _chunk_id_of(c)
            retrieved_ids.append(cid)
            score = float(scored_dict.get(cid, 0.0))
            is_gt = cid in expected
            retrieved_details.append({
                "chunk_id": cid,
                "title": c.get("title", ""),
                "text": c.get("text", ""),
                "score": round(score, 3),
                "is_ground_truth": is_gt,
            })

        hit = (not expected) or bool(expected & set(retrieved_ids))
        row = {
            "id": entry["id"],
            "question": q,
            "expected": sorted(expected),
            "retrieved_ids": retrieved_ids,
            "retrieved": retrieved_details,
            "hit": hit,
        }
        results.append(row)
        if expected and not hit:
            misses.append(row)

    return {
        "top_k": top_k,
        "noise_injection": noise,
        "passed": not misses,
        "hit_count": sum(1 for r in results if r["hit"]),
        "total": len(results),
        "retrieved_count": sum(len(r["retrieved"]) for r in results),
        "misses": misses,
        "results": results,
    }


@contextmanager
def _temporary_api_key(api_key: str | None):
    if not api_key:
        yield
        return
    previous = os.environ.get("OPENAI_API_KEY")
    os.environ["OPENAI_API_KEY"] = api_key
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("OPENAI_API_KEY", None)
        else:
            os.environ["OPENAI_API_KEY"] = previous


@app.post("/api/evaluate/live")
def evaluate_live(body: LiveRequest) -> dict[str, Any]:
    try:
        from rag_pipeline import run_rag_pipeline

        snapshots = load_snapshots()
        thresholds = dict(snapshots["default_thresholds"])
        if body.thresholds:
            thresholds.update({k: float(v) for k, v in body.thresholds.items() if k in thresholds})

        top_k = body.top_k
        prompt_mode = body.prompt_mode
        noise = body.noise_injection
        if body.preset_id:
            preset = preset_by_id(snapshots, body.preset_id)
            top_k = preset["config"]["top_k"]
            prompt_mode = preset["config"]["prompt_mode"]
            noise = preset["config"]["noise_injection"]

        benchmark = {row["id"]: row for row in load_benchmark()}
        entry = None
        if body.benchmark_id:
            entry = benchmark.get(body.benchmark_id)
            if entry is None:
                raise HTTPException(status_code=404, detail=f"Unknown benchmark id {body.benchmark_id!r}")
        question = body.question or (entry["question"] if entry else None)
        if not question:
            entry = next(iter(benchmark.values()))
            question = entry["question"]

        api_key = body.api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=400,
                detail="An OpenAI or Groq API key is required for live evaluation. Pass api_key or set OPENAI_API_KEY.",
            )

        with _temporary_api_key(api_key):
            result = run_rag_pipeline(
                question,
                top_k=top_k,
                prompt_mode=prompt_mode,
                noise_injection=noise,
                api_key=api_key,
            )
            metrics = _score_live(question, result, entry, thresholds, api_key=api_key)

        return {
            "question": question,
            "benchmark_id": entry["id"] if entry else None,
            "config": {
                "top_k": top_k,
                "prompt_mode": prompt_mode,
                "noise_injection": noise,
            },
            "answer": result.answer,
            "chunk_ids": result.chunk_ids,
            "contexts": result.contexts,
            "metrics": metrics,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _score_live(
    question: str,
    result: Any,
    entry: dict | None,
    thresholds: dict[str, float],
    api_key: str | None = None,
) -> dict[str, Any]:
    try:
        from deepeval.metrics import (
            AnswerRelevancyMetric,
            ContextualPrecisionMetric,
            ContextualRecallMetric,
            FaithfulnessMetric,
        )
        from deepeval.test_case import LLMTestCase
    except ImportError as exc:
        raise HTTPException(status_code=500, detail=f"DeepEval is not installed: {exc}") from exc

    model_arg = None
    if api_key and api_key.startswith("gsk_"):
        from deepeval.models.base_model import DeepEvalBaseLLM

        class GroqOpenAIModel(DeepEvalBaseLLM):
            def __init__(self, key: str, model_name: str = "openai/gpt-oss-120b"):
                self.key = key
                self.model_name = model_name
                super().__init__(model=model_name)

            def load_model(self):
                from openai import OpenAI
                return OpenAI(api_key=self.key, base_url="https://api.groq.com/openai/v1")

            def generate(self, prompt: str, schema=None, **kwargs) -> str:
                client = self.load_model()
                response = client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                )
                return (response.choices[0].message.content or "").strip()

            async def a_generate(self, prompt: str, schema=None, **kwargs) -> str:
                return self.generate(prompt)

            def get_model_name(self) -> str:
                return self.model_name

        model_arg = GroqOpenAIModel(api_key)

    expected = (entry or {}).get("ground_truth_answer") or result.answer
    test_case = LLMTestCase(
        input=question,
        actual_output=result.answer,
        retrieval_context=result.contexts or [""],
        expected_output=expected,
    )
    builders = [
        ("faithfulness", FaithfulnessMetric, thresholds["faithfulness"]),
        ("answer_relevancy", AnswerRelevancyMetric, thresholds["answer_relevancy"]),
        ("context_precision", ContextualPrecisionMetric, thresholds["context_precision"]),
        ("context_recall", ContextualRecallMetric, thresholds["context_recall"]),
    ]
    scored = {}
    for name, cls, threshold in builders:
        if model_arg:
            metric = cls(threshold=threshold, model=model_arg, include_reason=True)
        else:
            metric = cls(threshold=threshold, include_reason=True)
        metric.measure(test_case)
        score = float(metric.score or 0.0)
        scored[name] = {
            "score": score,
            "threshold": threshold,
            "passed": bool(metric.is_successful()),
            "reason": metric.reason or "",
        }
    return scored


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
