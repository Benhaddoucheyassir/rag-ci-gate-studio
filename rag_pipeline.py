"""A deliberately small reference RAG pipeline, so the CI gate has something to gate.

This exists to make tests/test_rag_gate.py runnable out of the box. It is not
the point of the repo. It is the placeholder you delete.

Retrieval is keyword scoring over corpus/chunks.jsonl using nothing but the
standard library, which keeps the repo installable without a vector database.
Generation is a single grounded OpenAI call that is instructed to answer only
from the retrieved chunks. That combination is enough to produce real,
non-trivial metric scores: it retrieves imperfectly, and it occasionally
answers past what the chunks actually support, which is exactly the behavior
the four metrics are built to catch.

Optional knobs used by the demo console (all default to the original CI
behavior so `run_rag_pipeline(question)` and `retrieve(question)` stay
backward-compatible with tests/test_rag_gate.py):

    top_k            how many chunks to hand the generator (default 3)
    prompt_mode      "strict" (grounded) vs "permissive" (may invent)
    noise_injection  mix unrelated corpus chunks into the retrieved set

To swap in your own pipeline, see the seam documented in
tests/test_rag_gate.py. You do not need to edit this file.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

CORPUS_PATH = Path(__file__).parent / "corpus" / "chunks.jsonl"

# How many chunks to hand the generator. Lower this and context recall drops
# because relevant chunks get cut off. Raise it and context precision drops
# because irrelevant chunks come along for the ride. Watching those two move
# in opposite directions is the fastest way to feel what they measure.
TOP_K = 3

GENERATION_MODEL = os.getenv("RAG_GENERATION_MODEL", "gpt-4o-mini")

STRICT_SYSTEM_PROMPT = (
    "You answer questions about the Meridian product using ONLY the reference "
    "passages provided. Be concise and specific: prefer the exact numbers, "
    "limits, and time windows stated in the passages. If the passages do not "
    "contain the answer, say so plainly instead of guessing."
)

PERMISSIVE_SYSTEM_PROMPT = (
    "You are a confident Meridian product expert. Use the reference passages "
    "as a starting point, but you may also draw on typical SaaS conventions, "
    "plausible SLAs, and adjacent product details to give a complete, helpful "
    "answer. Prefer a full answer over admitting gaps. Do not hedge."
)

SYSTEM_PROMPT = STRICT_SYSTEM_PROMPT
PROMPT_MODES = {
    "strict": STRICT_SYSTEM_PROMPT,
    "permissive": PERMISSIVE_SYSTEM_PROMPT,
}

# Words too common in this corpus to carry retrieval signal.
STOPWORDS = frozenset(
    """a about after all also am an and any are as at be been before being but by can
    cant could did do does doing dont for from get gets getting had has have how i if
    in into is it its just me my no not of on once only or our out over should so some
    than that the their them then there these they this to too us use using very was
    we were what when where which while who why will with would you your""".split()
)


@dataclass
class RagResult:
    """What a RAG pipeline has to return for all four metrics to be computable."""

    answer: str
    #: The chunk TEXTS handed to the generator. Ragas scores against these.
    contexts: list[str]
    #: The chunk IDs, in retrieved order. Compared against
    #: `ground_truth_chunk_ids` in the benchmark to sanity-check retrieval
    #: without paying for an LLM judge.
    chunk_ids: list[str] = field(default_factory=list)


def stem(word: str) -> str:
    """Fold the most common English suffixes so word forms match across a query.

    Crude on purpose, and still worth the fifteen lines. Without it, a user
    asking about "429s" never matches a doc that says "429", and "clients"
    never matches "client", which shows up as a context recall failure that
    looks like a retrieval bug but is really a tokenization bug.
    """
    for suffix, replacement in (("ies", "y"), ("sses", "ss"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: len(word) - len(suffix)] + replacement
    return word


def tokenize(text: str) -> list[str]:
    """Lowercase, stemmed word tokens with stopwords and one-character noise removed."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return [stem(w) for w in words if w not in STOPWORDS and len(w) > 1]


@lru_cache(maxsize=1)
def load_corpus(path: str = str(CORPUS_PATH)) -> tuple[dict, ...]:
    """Read corpus/chunks.jsonl once and cache it for the whole test session."""
    corpus_path = Path(path)
    if not corpus_path.exists():
        raise FileNotFoundError(
            f"Corpus not found at {corpus_path}. Expected a JSONL file with "
            "chunk_id, title, and text on every line."
        )
    chunks = []
    with corpus_path.open(encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{corpus_path}:{lineno} is not valid JSON: {exc}") from exc
            chunks.append(record)
    return tuple(chunks)


def _score_chunks(question: str) -> list[tuple[float, dict]]:
    query_terms = set(tokenize(question))
    if not query_terms:
        return []

    scored = []
    for chunk in load_corpus():
        chunk_terms = tokenize(f"{chunk['title']} {chunk['text']}")
        if not chunk_terms:
            continue
        overlap = sum(1 for term in chunk_terms if term in query_terms)
        if overlap == 0:
            continue
        # Reward matching many distinct query terms, penalize verbosity mildly.
        distinct = len(query_terms & set(chunk_terms))
        score = (distinct * 2 + overlap) / (len(chunk_terms) ** 0.5)
        scored.append((score, chunk))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored


def retrieve(
    question: str,
    top_k: int = TOP_K,
    noise_injection: bool = False,
) -> list[dict]:
    """Score every chunk against the question and return the best `top_k`.

    Overlap count normalized by chunk length: a long chunk that happens to
    contain the query words should not automatically beat a short chunk that
    is entirely about them.

    When `noise_injection` is True, unrelated corpus chunks are mixed into
    the result list so context precision collapses while recall can still
    hold if the relevant documents remain present.
    """
    if top_k < 1:
        return []

    scored = _score_chunks(question)
    ranked = [chunk for _, chunk in scored]

    if not noise_injection:
        return ranked[:top_k]

    # Keep a thin relevant prefix so recall can still pass, then pad with
    # documents the scorer never ranked (zero query overlap).
    keep_relevant = max(1, min(len(ranked), max(1, top_k // 3)))
    relevant = ranked[:keep_relevant]
    chosen_ids = {c["chunk_id"] for c in relevant}
    noise = [c for c in load_corpus() if c["chunk_id"] not in chosen_ids]
    mixed: list[dict] = []
    noise_i = 0
    rel_i = 0
    while len(mixed) < top_k and (rel_i < len(relevant) or noise_i < len(noise)):
        if rel_i < len(relevant) and (len(mixed) % 3 == 0 or noise_i >= len(noise)):
            mixed.append(relevant[rel_i])
            rel_i += 1
        elif noise_i < len(noise):
            mixed.append(noise[noise_i])
            noise_i += 1
        else:
            break
    return mixed[:top_k]


def generate(
    question: str,
    chunks: list[dict],
    prompt_mode: str = "strict",
    api_key: str | None = None,
) -> str:
    """Answer the question from the retrieved chunks with a single LLM call."""
    from openai import OpenAI

    if not chunks:
        return "I could not find anything in the documentation that answers that."

    system = PROMPT_MODES.get(prompt_mode)
    if system is None:
        raise ValueError(f"prompt_mode must be one of {sorted(PROMPT_MODES)}, got {prompt_mode!r}")

    passages = "\n\n".join(
        f"[{c['chunk_id']}] {c['title']}\n{c['text']}" for c in chunks
    )
    if api_key and api_key.startswith("gsk_"):
        client = OpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
        model = "openai/gpt-oss-120b"
    elif api_key:
        client = OpenAI(api_key=api_key)
        model = GENERATION_MODEL
    else:
        client = OpenAI()
        model = GENERATION_MODEL

    response = client.chat.completions.create(
        model=model,
        # Temperature 0 removes one source of variance from the pipeline. The
        # LLM JUDGE scoring the metrics is still non-deterministic, which is
        # the variance the repeated-run gate exists to absorb.
        temperature=0,
        messages=[
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"Reference passages:\n\n{passages}\n\nQuestion: {question}",
            },
        ],
    )
    return (response.choices[0].message.content or "").strip()


def run_rag_pipeline(
    question: str,
    top_k: int | None = None,
    prompt_mode: str = "strict",
    noise_injection: bool = False,
    api_key: str | None = None,
) -> RagResult:
    """Retrieve, then generate. This is the callable the CI gate targets.

    Extra keyword arguments are ignored by tests/test_rag_gate.py, which calls
    the function with a single question string.
    """
    k = TOP_K if top_k is None else top_k
    chunks = retrieve(question, top_k=k, noise_injection=noise_injection)
    return RagResult(
        answer=generate(question, chunks, prompt_mode=prompt_mode, api_key=api_key),
        contexts=[c["text"] for c in chunks],
        chunk_ids=[c["chunk_id"] for c in chunks],
    )


if __name__ == "__main__":
    import sys

    query = " ".join(sys.argv[1:]) or "how many api calls can I make on the team plan?"
    result = run_rag_pipeline(query)
    print(f"\nQ: {query}")
    print(f"Retrieved: {', '.join(result.chunk_ids) or '(nothing)'}")
    print(f"\nA: {result.answer}\n")
