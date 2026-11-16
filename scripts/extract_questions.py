#!/usr/bin/env python3
"""Mine candidate benchmark questions out of exported support logs.

    python scripts/extract_questions.py --input logs/ --output candidates.jsonl

Standard library only, on purpose. This is a grep with opinions, not a model.

WHAT THIS PRODUCES IS CANDIDATES, NOT TRUTH.
============================================
Every line written to the output file is a *suggestion for a human to review*.
Nothing here is a graded benchmark entry, and nothing here has a ground-truth
answer, because a ground-truth answer requires a person who knows the product
to read the source documents and write the correct answer down. Feeding this
output straight into an evaluation run would score your RAG system against
questions nobody verified are answerable, which is worse than not measuring at
all: it produces a number that looks rigorous and means nothing.

The workflow this is built for:

    1. Run this over a week of exported tickets or chat logs.
    2. Skim the JSONL. Most of it is noise. Delete the noise.
    3. For each keeper, find the chunk(s) in your corpus that answer it and
       write the ground-truth answer yourself.
    4. Promote the survivors into benchmark/rag_benchmark_vN.jsonl.

Steps 2 and 3 are the whole job. This script only saves you step 1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

# Files worth scanning. Anything else in the folder is skipped silently.
TEXT_SUFFIXES = {".txt", ".md", ".log", ".csv", ".jsonl", ".json"}

# A question shorter than this is almost always a fragment ("what?", "really?")
# or an agent's own clarifier ("this one?"). Raise it if your logs are noisy.
MIN_QUESTION_CHARS = 20
MAX_QUESTION_CHARS = 300

# Conversational scaffolding that shows up at the front of real support lines.
# Stripped before the length check so "hi there, how do I rotate an api key?"
# is measured on the part that matters.
GREETING_PREFIXES = re.compile(
    r"^(?:"
    r"hi+|hey+|hello|good\s+(?:morning|afternoon|evening)|"
    r"thanks?|thank\s+you|sorry|excuse\s+me|quick\s+(?:one|question)|"
    r"just\s+wondering|hope\s+(?:you|this)\s+\w+|"
    r"also|and|so|oh|actually|btw|by\s+the\s+way"
    r")\b[\s,.!:-]*",
    re.IGNORECASE,
)

# Transcript line prefixes: "Customer:", "[14:03] user >", "2026-03-11 agent:".
SPEAKER_PREFIX = re.compile(
    r"^\s*(?:\[?\d{1,4}[-:/]\d{1,2}(?:[-:/]\d{1,4})?\]?\s*)?"
    r"(?:\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s*)?"
    r"(?:(?P<speaker>[A-Za-z][\w .'-]{0,30})\s*[:>]\s*)?",
)

# Lines the SUPPORT AGENT asked, not the user. Keeping these poisons the
# benchmark with internal phrasing your users never use.
AGENT_SPEAKERS = {
    "agent", "support", "admin", "bot", "assistant", "system",
    "operator", "staff", "moderator", "help", "helpdesk",
}

# Boilerplate questions that appear in every ticket and answer nothing about
# the product.
BOILERPLATE = re.compile(
    r"^(?:"
    r"(?:is\s+)?(?:there\s+)?anything\s+else|"
    r"(?:does\s+)?that\s+(?:help|make\s+sense|work)|"
    r"(?:are\s+)?you\s+(?:still\s+)?there|"
    r"can\s+you\s+hear\s+me|"
    r"how\s+are\s+you|"
    r"(?:may|can)\s+i\s+(?:have|get)\s+your\s+(?:email|name|order|account)"
    r")",
    re.IGNORECASE,
)

# Anything that looks like a secret or a personal identifier. A candidate
# carrying one gets dropped rather than written to a file that ends up in git.
#
# The credential branch allows underscores and dashes inside the token, so
# "sk_live_abcdefgh12345678" is caught and not just "sk_abcdefgh12345678", and
# it requires at least one digit in the tail. That digit requirement is what
# keeps ordinary prose like "the key_management_system" from being flagged.
# When in doubt this drops the candidate: losing one reviewable question costs
# nothing, and writing a live key into a committed file costs a rotation.
SENSITIVE = re.compile(
    r"(?:"
    r"[\w.+-]+@[\w-]+\.[\w.]+"                       # email address
    r"|\b(?:sk|pk|api|key|token|bearer)[-_](?=[A-Za-z0-9_-]*\d)[A-Za-z0-9_-]{8,}"
    r"|\b(?:\d[ -]?){13,19}\b"                       # card-length digit run
    r")",
    re.IGNORECASE,
)


def iter_lines(root: Path):
    """Yield (path, line_number, text) for every text-ish line under root.

    JSON and JSONL files get their string values pulled out, since exported
    chat logs are usually a list of message objects rather than raw text.
    """
    paths = sorted(root.rglob("*")) if root.is_dir() else [root]
    for path in paths:
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            raw = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"skipping {path}: {exc}", file=sys.stderr)
            continue

        if path.suffix.lower() in {".json", ".jsonl"}:
            for lineno, text in enumerate(_iter_json_strings(raw), start=1):
                yield path, lineno, text
        else:
            for lineno, text in enumerate(raw.splitlines(), start=1):
                yield path, lineno, text


def _iter_json_strings(raw: str):
    """Pull every string leaf out of a JSON or JSONL blob, in document order."""

    def walk(node):
        if isinstance(node, str):
            yield node
        elif isinstance(node, dict):
            for value in node.values():
                yield from walk(value)
        elif isinstance(node, list):
            for value in node:
                yield from walk(value)

    try:
        yield from walk(json.loads(raw))
        return
    except json.JSONDecodeError:
        pass

    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            yield from walk(json.loads(line))
        except json.JSONDecodeError:
            yield line


def extract_question(
    line: str,
    min_chars: int = MIN_QUESTION_CHARS,
) -> tuple[str, str | None] | None:
    """Return (question, speaker) if this line looks like a user question.

    Returns None for everything that fails a heuristic. Being aggressive here
    is correct: a human still reviews whatever survives, and a smaller pile
    with less junk in it actually gets reviewed.
    """
    match = SPEAKER_PREFIX.match(line)
    speaker = (match.group("speaker") or "").strip().lower() if match else ""
    body = line[match.end():] if match else line

    # Drop the agent's own questions.
    if speaker and speaker.rstrip("s") in AGENT_SPEAKERS:
        return None

    body = GREETING_PREFIXES.sub("", body.strip())

    # A single line can contain several sentences. Take the last one that is a
    # question, which in support text is almost always the actual ask.
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", body) if s.strip()]
    question = next((s for s in reversed(sentences) if s.endswith("?")), None)
    if question is None:
        return None

    question = GREETING_PREFIXES.sub("", question).strip()

    if not (min_chars <= len(question) <= MAX_QUESTION_CHARS):
        return None
    if BOILERPLATE.match(question):
        return None
    if SENSITIVE.search(question):
        return None
    # Needs at least four words to be a real question rather than a fragment.
    if len(question.split()) < 4:
        return None

    return question, (speaker or None)


def normalize(question: str) -> str:
    """Fold casing, whitespace, punctuation, and accents for de-duplication.

    "How do I rotate an API key?" and "how do i rotate an api key ??" are the
    same question and should only be reviewed once.
    """
    folded = unicodedata.normalize("NFKD", question)
    folded = "".join(c for c in folded if not unicodedata.combining(c))
    folded = folded.casefold()
    folded = re.sub(r"[^\w\s]", " ", folded)
    return re.sub(r"\s+", " ", folded).strip()


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Mine candidate benchmark questions from exported support tickets "
            "or chat logs. Output is CANDIDATES for human review, never "
            "auto-graded ground truth."
        )
    )
    parser.add_argument(
        "--input", required=True, type=Path,
        help="File or folder of exported logs to scan (recursive).",
    )
    parser.add_argument(
        "--output", required=True, type=Path,
        help="Where to write the JSONL candidates.",
    )
    parser.add_argument(
        "--min-chars", type=int, default=MIN_QUESTION_CHARS,
        help=f"Minimum question length in characters (default {MIN_QUESTION_CHARS}).",
    )
    parser.add_argument(
        "--limit", type=int, default=0,
        help="Stop after N unique candidates. 0 means no limit.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: input path does not exist: {args.input}", file=sys.stderr)
        return 1

    seen: dict[str, dict] = {}
    scanned = 0

    for path, lineno, line in iter_lines(args.input):
        scanned += 1
        found = extract_question(line, min_chars=args.min_chars)
        if found is None:
            continue
        question, speaker = found
        key = normalize(question)

        if key in seen:
            # Already have this question. Record that it came up again, which
            # is the single most useful signal for deciding what to review first.
            seen[key]["occurrences"] += 1
            continue

        seen[key] = {
            "question": question,
            "normalized": key,
            "occurrences": 1,
            "speaker": speaker,
            "source_file": str(path),
            "source_line": lineno,
            # Deliberately empty. A human fills these in during review.
            "ground_truth_answer": None,
            "ground_truth_chunk_ids": [],
            "reviewed": False,
        }

        if args.limit and len(seen) >= args.limit:
            break

    # Most-repeated questions first, so the reviewer's first ten minutes go to
    # whatever users actually keep asking.
    candidates = sorted(seen.values(), key=lambda c: (-c["occurrences"], c["question"]))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for candidate in candidates:
            handle.write(json.dumps(candidate, ensure_ascii=False) + "\n")

    print(f"scanned {scanned} lines under {args.input}")
    print(f"wrote {len(candidates)} unique candidates to {args.output}")
    print("These are CANDIDATES. Review them, write the ground truth by hand,")
    print("then promote the keepers into benchmark/rag_benchmark_vN.jsonl.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
