"""The pass/fail CI gate. This is the file the whole repo exists for.

    pytest tests/test_rag_gate.py

What it does, in order:

    1. Loads the versioned benchmark (benchmark/rag_benchmark_v3.jsonl).
    2. Runs YOUR RAG pipeline over every benchmark question.
    3. Scores the results with Ragas on all four metrics.
    4. Repeats steps 2 and 3 `GATE_RUNS` times.
    5. Asserts each metric cleared its own threshold in at least
       `REQUIRED_PASSING_RUNS` of those runs.

Two design decisions carry the whole thing.

FIRST: a separate threshold per metric, never one blended average. A system
that is 95 percent faithful and 60 percent relevant averages out to something
that looks acceptable while actively failing users on relevancy. Averaging
destroys the one piece of information you needed.

SECOND: gate on a pass RATE across repeated runs, not a single verdict. The
judge scoring these metrics is itself a non-deterministic LLM. A gate that
fails on ordinary judge variance gets disabled by the team inside a sprint,
and a disabled gate is worse than no gate because everyone still believes it
is running. Four passes out of five is a defensible floor. A question that
drifts from five-of-five to two-of-five over a week is real signal, and it is
signal a single-run gate can never surface.
"""

from __future__ import annotations

import importlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path

import pytest
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

# ---------------------------------------------------------------------------
# Thresholds. Tune these; they are the dial the whole gate turns on.
#
# Faithfulness and context recall sit higher because their failures are the
# ones you genuinely cannot ship: an invented fact stated confidently, or a
# missing chunk that made the correct answer unreachable in the first place.
#
# Answer relevancy and context precision get more room because their failures
# are rough edges rather than wrong answers: an over-broad retrieval that
# dragged in a neighbouring chunk, or an answer that wandered one sentence
# past what was asked.
#
# Start here, watch a week of real runs, then move them. Do not move them
# because a build went red once.
# ---------------------------------------------------------------------------
FAITHFULNESS_THRESHOLD = 0.90
ANSWER_RELEVANCY_THRESHOLD = 0.80
CONTEXT_PRECISION_THRESHOLD = 0.75
CONTEXT_RECALL_THRESHOLD = 0.90

# Repeated-run gate. Five runs, four of which must clear the threshold.
# Override GATE_RUNS down to 1 for a fast local smoke check; leave it at 5 in CI.
GATE_RUNS = int(os.getenv("RAG_GATE_RUNS", "5"))
REQUIRED_PASSING_RUNS = int(os.getenv("RAG_GATE_REQUIRED_PASSES", "4"))

BENCHMARK_PATH = Path(
    os.getenv("RAG_BENCHMARK", Path(__file__).parent.parent / "benchmark" / "rag_benchmark_v3.jsonl")
)

# ---------------------------------------------------------------------------
# THE SEAM: point this at your own RAG pipeline.
#
# Set RAG_PIPELINE to "your_module:your_callable". The callable takes a single
# question string and returns anything exposing:
#
#     .answer    -> str        the generated answer
#     .contexts  -> list[str]  the chunk TEXTS your retriever returned
#
# A plain dict with "answer" and "contexts" keys works too, as does a tuple of
# (answer, contexts). Nothing else in this file needs to change.
#
#     export RAG_PIPELINE="myapp.rag:answer_question"
#     pytest tests/test_rag_gate.py
#
# The default below is the throwaway reference pipeline in rag_pipeline.py,
# there only so this gate runs before you have wired anything up.
# ---------------------------------------------------------------------------
PIPELINE_TARGET = os.getenv("RAG_PIPELINE", "rag_pipeline:run_rag_pipeline")


def load_pipeline():
    """Import the configured pipeline callable from its "module:function" string."""
    if ":" not in PIPELINE_TARGET:
        raise ValueError(
            f'RAG_PIPELINE must look like "module:callable", got {PIPELINE_TARGET!r}'
        )
    module_name, attr = PIPELINE_TARGET.split(":", 1)
    module = importlib.import_module(module_name)
    pipeline = getattr(module, attr, None)
    if not callable(pipeline):
        raise TypeError(f"{PIPELINE_TARGET} is not callable")
    return pipeline


def unpack(result) -> tuple[str, list[str]]:
    """Normalize whatever the pipeline returned into (answer, contexts)."""
    if hasattr(result, "answer") and hasattr(result, "contexts"):
        return result.answer, list(result.contexts)
    if isinstance(result, dict):
        return result["answer"], list(result["contexts"])
    if isinstance(result, (tuple, list)) and len(result) == 2:
        return result[0], list(result[1])
    raise TypeError(
        "Pipeline must return an object with .answer/.contexts, a dict with "
        f"those keys, or an (answer, contexts) pair. Got {type(result).__name__}."
    )


def load_benchmark() -> list[dict]:
    """Read the versioned benchmark and fail loudly on a malformed entry."""
    if not BENCHMARK_PATH.exists():
        raise FileNotFoundError(f"Benchmark not found at {BENCHMARK_PATH}")

    required = {"id", "question", "ground_truth_answer", "ground_truth_chunk_ids"}
    entries = []
    with BENCHMARK_PATH.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            missing = required - entry.keys()
            if missing:
                raise ValueError(
                    f"{BENCHMARK_PATH.name}:{lineno} is missing {sorted(missing)}. "
                    "A benchmark entry without ground truth cannot be scored."
                )
            entries.append(entry)

    if not entries:
        raise ValueError(f"{BENCHMARK_PATH} is empty. Nothing to gate on.")
    return entries


# (metric object, threshold, human label). Indexing the Ragas result by
# `metric.name` rather than a hardcoded string keeps this working across Ragas
# versions, which rename some metric columns.
GATED_METRICS = [
    (faithfulness, FAITHFULNESS_THRESHOLD, "faithfulness"),
    (answer_relevancy, ANSWER_RELEVANCY_THRESHOLD, "answer relevancy"),
    (context_precision, CONTEXT_PRECISION_THRESHOLD, "context precision"),
    (context_recall, CONTEXT_RECALL_THRESHOLD, "context recall"),
]


@dataclass
class RunScores:
    """One full pass over the benchmark: mean score per metric."""

    run_index: int
    scores: dict[str, float]


def score_once(run_index: int, pipeline, benchmark: list[dict]) -> RunScores:
    """Run the pipeline over the whole benchmark and score it with Ragas once."""
    questions, answers, contexts, references = [], [], [], []

    for entry in benchmark:
        answer, retrieved = unpack(pipeline(entry["question"]))
        questions.append(entry["question"])
        answers.append(answer)
        # Ragas needs a non-empty context list; an empty retrieval is a real
        # failure and should score zero rather than crash the run.
        contexts.append(retrieved or [""])
        references.append(entry["ground_truth_answer"])

    dataset = Dataset.from_dict(
        {
            "user_input": questions,
            "response": answers,
            "retrieved_contexts": contexts,
            "reference": references,
        }
    )
    frame = evaluate(
        dataset=dataset,
        metrics=[metric for metric, _, _ in GATED_METRICS],
    ).to_pandas()

    return RunScores(
        run_index=run_index,
        scores={metric.name: float(frame[metric.name].mean()) for metric, _, _ in GATED_METRICS},
    )


@pytest.fixture(scope="session")
def gate_runs() -> list[RunScores]:
    """Score the benchmark GATE_RUNS times. Session-scoped: this is the expensive part.

    Every gated metric reads from this one fixture, so the benchmark is scored
    GATE_RUNS times total, not GATE_RUNS times per metric.
    """
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is not set; the LLM judge cannot run.")

    pipeline = load_pipeline()
    benchmark = load_benchmark()
    results = [score_once(i, pipeline, benchmark) for i in range(1, GATE_RUNS + 1)]

    print(f"\nBenchmark: {BENCHMARK_PATH.name} ({len(benchmark)} questions)")
    print(f"Pipeline : {PIPELINE_TARGET}")
    print(f"Runs     : {GATE_RUNS}, need {REQUIRED_PASSING_RUNS} passing\n")
    return results


@pytest.mark.parametrize(
    ("metric", "threshold", "label"),
    GATED_METRICS,
    ids=[label.replace(" ", "_") for _, _, label in GATED_METRICS],
)
def test_metric_clears_threshold_across_runs(gate_runs, metric, threshold, label):
    """Each metric must clear its own threshold in at least N of M runs."""
    observed = [run.scores[metric.name] for run in gate_runs]

    # A NaN means the judge failed to produce a score for that run. Counting it
    # as a pass would let a broken judge wave a regression through.
    passing = [s for s in observed if not math.isnan(s) and s >= threshold]
    formatted = ", ".join("nan" if math.isnan(s) else f"{s:.3f}" for s in observed)

    print(
        f"{label:<20} threshold {threshold:.2f}  "
        f"runs [{formatted}]  passed {len(passing)}/{len(observed)}"
    )

    assert len(passing) >= REQUIRED_PASSING_RUNS, (
        f"{label} cleared {threshold:.2f} in only {len(passing)} of {len(observed)} runs "
        f"(needed {REQUIRED_PASSING_RUNS}). Per-run means: [{formatted}]. "
        f"{'Consistently below threshold, so this is a real regression, not judge noise.' if not passing else 'Borderline: check whether the drop is a regression or a threshold set too tight for this benchmark.'}"
    )


def test_retrieval_hits_ground_truth_chunks():
    """A free, deterministic retrieval check that runs with no LLM at all.

    Context recall is the LLM-judged version of this question. But because the
    benchmark records `ground_truth_chunk_ids`, you can catch an outright
    broken retriever in milliseconds and for zero dollars, before spending
    anything on judges. Run this one on every commit and the expensive gate
    above only on pull requests.

    Point RAG_RETRIEVER at a retrieval-only callable that takes a question and
    returns chunks (dicts with a "chunk_id" key, objects with a .chunk_id
    attribute, or plain ID strings). Skipped if it is not importable.
    """
    target = os.getenv("RAG_RETRIEVER", "rag_pipeline:retrieve")
    module_name, _, attr = target.partition(":")
    try:
        retriever = getattr(importlib.import_module(module_name), attr)
    except (ImportError, AttributeError):
        pytest.skip(
            f"No retrieval-only callable at {target}; the context recall gate covers this."
        )

    def chunk_id_of(chunk):
        if isinstance(chunk, str):
            return chunk
        if isinstance(chunk, dict):
            return chunk.get("chunk_id")
        return getattr(chunk, "chunk_id", None)

    misses = []
    for entry in load_benchmark():
        retrieved = [chunk_id_of(c) for c in retriever(entry["question"])]
        expected = set(entry["ground_truth_chunk_ids"])
        # At least one ground-truth chunk must show up. Requiring all of them
        # is a stricter gate worth turning on once retrieval is solid.
        if expected and not (expected & set(retrieved)):
            misses.append(f"  {entry['id']}: expected any of {sorted(expected)}, got {retrieved}")

    assert not misses, (
        f"Retrieval returned none of the ground-truth chunks for {len(misses)} "
        "benchmark questions:\n" + "\n".join(misses)
    )
