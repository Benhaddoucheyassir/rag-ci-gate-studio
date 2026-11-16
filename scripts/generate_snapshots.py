#!/usr/bin/env python3
"""Write canned 5-run demo snapshots for the evaluation console.

    python scripts/generate_snapshots.py

These are not live Ragas/DeepEval scores. They are realistic, hand-authored
traces that match what the four presets actually do to the reference pipeline:

    healthy_baseline      top_k=3, strict, no noise
    broken_retriever      top_k=1, strict, no noise
    hallucinating_prompt  top_k=3, permissive, no noise
    noisy_context         top_k=6, strict, noise injection

`backend/main.py` recomputes pass/fail from the stored per-run scores whenever
the UI moves a threshold. Reasons are written in DeepEval's natural-language
voice so the console has something to read without spending an API call.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "backend" / "demo_snapshots.json"

GATE_RUNS = 5
REQUIRED_PASSING_RUNS = 4
DEFAULT_THRESHOLDS = {
    "faithfulness": 0.90,
    "answer_relevancy": 0.80,
    "context_precision": 0.75,
    "context_recall": 0.90,
}

METRIC_LABELS = {
    "faithfulness": "Faithfulness",
    "answer_relevancy": "Answer Relevancy",
    "context_precision": "Context Precision",
    "context_recall": "Context Recall",
}


def run(index: int, scores: dict[str, float], reasons: dict[str, str]) -> dict:
    return {"run_index": index, "scores": scores, "reasons": reasons}


PRESETS = [
    {
        "id": "healthy_baseline",
        "title": "Healthy baseline",
        "description": (
            "Default reference pipeline: top_k=3, strict grounding. Clears all four "
            "thresholds (0.90 / 0.80 / 0.75 / 0.90). Faithfulness shows realistic "
            "judge variance at 4/5 — one run dips just under 0.90."
        ),
        "config": {"top_k": 3, "prompt_mode": "strict", "noise_injection": False},
        "runs": [
            run(
                1,
                {
                    "faithfulness": 0.942,
                    "answer_relevancy": 0.861,
                    "context_precision": 0.812,
                    "context_recall": 0.961,
                },
                {
                    "faithfulness": (
                        "The actual output's claims about 00:00 UTC invoice generation, "
                        "the 600 rpm Team limit, and the 14-day invite window are all "
                        "supported by the retrieved passages. No extra facts were introduced."
                    ),
                    "answer_relevancy": (
                        "Each answer addresses the question that was asked. The Team-plan "
                        "rate-limit reply stays on throughput and the sliding window; it "
                        "does not wander into billing."
                    ),
                    "context_precision": (
                        "Most retrieved chunks are relevant. A neighbouring billing-cycle "
                        "chunk appeared once beside an upgrade question, which is why the "
                        "score is high but not perfect."
                    ),
                    "context_recall": (
                        "Ground-truth chunks (kb-billing-001, kb-ratelimit-001, "
                        "kb-onboarding-001, kb-sso-001, and the refund pair) were present "
                        "in retrieval for every benchmark question."
                    ),
                },
            ),
            run(
                2,
                {
                    "faithfulness": 0.921,
                    "answer_relevancy": 0.878,
                    "context_precision": 0.794,
                    "context_recall": 0.948,
                },
                {
                    "faithfulness": (
                        "Statements about Retry-After, exponential backoff, and bulk "
                        "endpoints counting as ten requests match kb-ratelimit-002. The "
                        "judge found no unsupported numeric claims in this run."
                    ),
                    "answer_relevancy": (
                        "Answers stay on-topic. The declined-card reply covers retries, "
                        "read-only mode, and the 30-day retention window asked about."
                    ),
                    "context_precision": (
                        "Retrieved contexts are mostly on-subject. One SSO chunk leaked "
                        "into a billing question via shared 'workspace Admin' wording."
                    ),
                    "context_recall": (
                        "Required chunks were retrieved for all eight questions. The "
                        "upgrade question included both kb-billing-002 and kb-billing-001."
                    ),
                },
            ),
            run(
                3,
                {
                    "faithfulness": 0.884,
                    "answer_relevancy": 0.844,
                    "context_precision": 0.831,
                    "context_recall": 0.972,
                },
                {
                    "faithfulness": (
                        "The answer correctly cites 00:00 UTC invoicing, then adds that "
                        "annual invoices are generated 'on the same calendar day as monthly "
                        "ones'. The passage only says annual plans are billed once for "
                        "twelve months upfront. That extra timing claim is unsupported and "
                        "pulled this run just under the 0.90 faithfulness threshold — "
                        "ordinary judge-plus-generator variance, not a broken pipeline."
                    ),
                    "answer_relevancy": (
                        "Slightly broader than the question on the refund case (mentions "
                        "overage charges without being asked) but still answers the ask."
                    ),
                    "context_precision": (
                        "Precision ticked up this run: the 429 question retrieved only "
                        "kb-ratelimit-002 and kb-ratelimit-001, with no SSO/onboarding noise."
                    ),
                    "context_recall": (
                        "All ground-truth chunk IDs appeared in the retrieved set. Recall "
                        "is not the failure mode on this preset."
                    ),
                },
            ),
            run(
                4,
                {
                    "faithfulness": 0.957,
                    "answer_relevancy": 0.869,
                    "context_precision": 0.805,
                    "context_recall": 0.954,
                },
                {
                    "faithfulness": (
                        "Refund, SSO, and rate-limit answers quote the source windows "
                        "(14 days, Enterprise-only Okta, sliding 60 second window) without "
                        "embellishment. Every claim is attributable to a retrieved chunk."
                    ),
                    "answer_relevancy": (
                        "Outputs are concise and question-aligned. No neighbouring-topic "
                        "drift on the mid-cycle upgrade question."
                    ),
                    "context_precision": (
                        "Three-chunk windows stay tight. The invite-expiry question "
                        "retrieved kb-onboarding-001 plus a weakly related sources chunk."
                    ),
                    "context_recall": (
                        "kb-refunds-001 and kb-refunds-002 both surfaced for the three-week "
                        "cancellation question, which is what the ground-truth list requires."
                    ),
                },
            ),
            run(
                5,
                {
                    "faithfulness": 0.933,
                    "answer_relevancy": 0.852,
                    "context_precision": 0.778,
                    "context_recall": 0.939,
                },
                {
                    "faithfulness": (
                        "Claims remain grounded. The judge noted one hedged sentence "
                        "('typically emailed within minutes') that is not in the passage, "
                        "but it was not stated as fact and did not sink the score."
                    ),
                    "answer_relevancy": (
                        "All eight answers address the user phrasing, including the typo'd "
                        "'429s' and 'do i get charged twice' questions."
                    ),
                    "context_precision": (
                        "A little more neighbour-chunk bleed than run 4 (onboarding next "
                        "to billing). Still clears 0.75 with room."
                    ),
                    "context_recall": (
                        "Ground-truth chunks present for every question. Mean recall stays "
                        "comfortably above 0.90."
                    ),
                },
            ),
        ],
    },
    {
        "id": "broken_retriever",
        "title": "Broken retriever",
        "description": (
            "top_k=1, strict prompt. The generator stays faithful to the single "
            "chunk it is given, so Faithfulness passes 5/5. Context Recall fails "
            "0/5 because the rest of the supporting documents never enter the window."
        ),
        "config": {"top_k": 1, "prompt_mode": "strict", "noise_injection": False},
        "runs": [
            run(
                1,
                {
                    "faithfulness": 0.961,
                    "answer_relevancy": 0.742,
                    "context_precision": 0.688,
                    "context_recall": 0.312,
                },
                {
                    "faithfulness": (
                        "The model refused to go past the single retrieved chunk. For the "
                        "429 question it only restated Retry-After and did not invent "
                        "bulk-endpoint math. Faithful, and incomplete."
                    ),
                    "answer_relevancy": (
                        "Several answers are partial. The upgrade question never mentions "
                        "proration because kb-billing-002 was not retrieved."
                    ),
                    "context_precision": (
                        "The one retrieved chunk is often on-topic, but not always the "
                        "chunk the benchmark marks as required, which caps precision."
                    ),
                    "context_recall": (
                        "top_k=1 cannot cover questions whose ground_truth_chunk_ids list "
                        "two documents (upgrade, 429s, refunds). Even single-chunk questions "
                        "miss when keyword scoring returns a neighbour instead of the gold "
                        "chunk. Recall is 0/5 against the 0.90 threshold."
                    ),
                },
            ),
            run(
                2,
                {
                    "faithfulness": 0.974,
                    "answer_relevancy": 0.728,
                    "context_precision": 0.671,
                    "context_recall": 0.286,
                },
                {
                    "faithfulness": (
                        "No hallucinated SLAs or extra numbers. The generator said 'the "
                        "passages do not contain the rest of that answer' wherever the "
                        "single chunk ran out — exactly what the strict prompt asks for."
                    ),
                    "answer_relevancy": (
                        "Answers address a slice of the question and omit the rest. The "
                        "declined-card reply never reaches the 30-day retention fact."
                    ),
                    "context_precision": (
                        "Precision is the wrong diagnosis here: the window is tiny, not "
                        "noisy. The score still sits under 0.75 because the retrieved "
                        "chunk is frequently a near-miss."
                    ),
                    "context_recall": (
                        "Gold chunks absent for bench-002, bench-004, and bench-006 in "
                        "this run. Context Recall remains far below 0.90."
                    ),
                },
            ),
            run(
                3,
                {
                    "faithfulness": 0.948,
                    "answer_relevancy": 0.755,
                    "context_precision": 0.704,
                    "context_recall": 0.341,
                },
                {
                    "faithfulness": (
                        "Still fully grounded in the one passage. The Okta question was "
                        "answered from kb-sso-001 only, with no invented IdP list extras."
                    ),
                    "answer_relevancy": (
                        "Slightly more complete this run on rate limits, but refund and "
                        "upgrade answers still miss half of what was asked."
                    ),
                    "context_precision": (
                        "The retrieved chunk for bench-003 was kb-ratelimit-001, which is "
                        "relevant. Other rows retrieved a related-but-wrong neighbour."
                    ),
                    "context_recall": (
                        "Missing kb-billing-002, kb-ratelimit-001 (on the 429 question), "
                        "and kb-refunds-002. Recall cannot clear 0.90 with top_k=1."
                    ),
                },
            ),
            run(
                4,
                {
                    "faithfulness": 0.966,
                    "answer_relevancy": 0.719,
                    "context_precision": 0.659,
                    "context_recall": 0.298,
                },
                {
                    "faithfulness": (
                        "FaithfulnessMetric: every sentence in the actual output can be "
                        "attributed to the single retrieval_context item. No unsupported "
                        "claims. Score 0.97."
                    ),
                    "answer_relevancy": (
                        "The output is relevant to a subset of the input. Users asking "
                        "how to handle 429s do not get backoff-plus-headers-plus-bulk."
                    ),
                    "context_precision": (
                        "ContextualPrecisionMetric: rank-1 is relevant on four of eight "
                        "rows and a near-miss on the rest."
                    ),
                    "context_recall": (
                        "ContextualRecallMetric: expected chunks are missing from "
                        "retrieval_context on most rows. This is a retrieval failure, "
                        "not a generation failure."
                    ),
                },
            ),
            run(
                5,
                {
                    "faithfulness": 0.953,
                    "answer_relevancy": 0.736,
                    "context_precision": 0.682,
                    "context_recall": 0.324,
                },
                {
                    "faithfulness": (
                        "Strict mode continues to refuse guesswork. Faithfulness passes "
                        "5/5 on this preset even while the gate as a whole is BLOCKED."
                    ),
                    "answer_relevancy": (
                        "Incomplete answers drag relevancy under 0.80. The gate would "
                        "also fail this metric; the headline failure is still recall."
                    ),
                    "context_precision": (
                        "One-chunk windows are not 'precise' when the chunk is the wrong "
                        "one. Precision does not rescue a broken retriever."
                    ),
                    "context_recall": (
                        "0/5 runs clear 0.90. Lowering top_k until the supporting document "
                        "falls off the list is the textbook recall failure."
                    ),
                },
            ),
        ],
    },
    {
        "id": "hallucinating_prompt",
        "title": "Hallucinating prompt",
        "description": (
            "top_k=3 with the permissive system prompt. Retrieval is healthy "
            "(precision and recall pass) but the generator invents SLAs, support "
            "tiers, and extra numbers. Faithfulness fails at 1/5."
        ),
        "config": {"top_k": 3, "prompt_mode": "permissive", "noise_injection": False},
        "runs": [
            run(
                1,
                {
                    "faithfulness": 0.712,
                    "answer_relevancy": 0.881,
                    "context_precision": 0.808,
                    "context_recall": 0.944,
                },
                {
                    "faithfulness": (
                        "FaithfulnessMetric: the answer claims a 99.9% uptime SLA and "
                        "'24-hour dedicated Slack support on Team', neither of which "
                        "appears in the retrieved passages. The 600 rpm figure is "
                        "supported; the surrounding embellishment is not."
                    ),
                    "answer_relevancy": (
                        "The output does answer the questions asked — it is helpful and "
                        "on-topic. Relevancy does not catch invented facts."
                    ),
                    "context_precision": (
                        "Retrieved chunks match the healthy baseline. The failure is "
                        "generation, not retrieval."
                    ),
                    "context_recall": (
                        "Gold chunks are present. The model had the evidence and still "
                        "wrote past it."
                    ),
                },
            ),
            run(
                2,
                {
                    "faithfulness": 0.644,
                    "answer_relevancy": 0.896,
                    "context_precision": 0.821,
                    "context_recall": 0.958,
                },
                {
                    "faithfulness": (
                        "Unsupported claims: invoices are 'usually delivered within 15 "
                        "minutes of generation'; declined cards trigger 'an automatic "
                        "pause on API keys after 48 hours'; refunds can be 'applied as "
                        "account credit if requested'. None of these statements are in "
                        "kb-billing-001, kb-billing-003, or kb-refunds-002 (which "
                        "explicitly says refunds cannot be issued as account credit)."
                    ),
                    "answer_relevancy": (
                        "Fluent, question-shaped answers. The judge scored relevancy "
                        "high because the extra claims still concern billing and refunds."
                    ),
                    "context_precision": (
                        "Context is clean. Precision passing alongside faithfulness "
                        "failing is the signature of a prompt problem."
                    ),
                    "context_recall": (
                        "Required documents retrieved. Recall is not the lever to pull."
                    ),
                },
            ),
            run(
                3,
                {
                    "faithfulness": 0.821,
                    "answer_relevancy": 0.872,
                    "context_precision": 0.793,
                    "context_recall": 0.931,
                },
                {
                    "faithfulness": (
                        "Fewer inventions this run, but the 429 answer still adds "
                        "'Meridian will page an on-call engineer if 429s persist for "
                        "ten minutes', which is not in kb-ratelimit-002. Score 0.82, "
                        "still under 0.90."
                    ),
                    "answer_relevancy": (
                        "Answers remain directed at the user questions, including the "
                        "Okta/Enterprise ask."
                    ),
                    "context_precision": (
                        "Same three-chunk retrieval quality as the healthy preset."
                    ),
                    "context_recall": (
                        "Ground-truth chunk IDs hit. The permissive prompt is the only "
                        "changed variable."
                    ),
                },
            ),
            run(
                4,
                {
                    "faithfulness": 0.913,
                    "answer_relevancy": 0.888,
                    "context_precision": 0.816,
                    "context_recall": 0.949,
                },
                {
                    "faithfulness": (
                        "This is the one run in five that stays mostly inside the "
                        "passages. A single hedged aside ('some teams treat bulk "
                        "endpoints as a burst allowance') was not treated as a hard "
                        "claim. Score 0.91, the only faithfulness pass on this preset."
                    ),
                    "answer_relevancy": (
                        "On-topic throughout. Permissive tone without the usual extra "
                        "product facts."
                    ),
                    "context_precision": (
                        "Relevant chunks dominate the window. Precision clears 0.75."
                    ),
                    "context_recall": (
                        "Gold set covered. Judge variance on faithfulness is why the "
                        "gate needs 4/5, not 1/5."
                    ),
                },
            ),
            run(
                5,
                {
                    "faithfulness": 0.681,
                    "answer_relevancy": 0.864,
                    "context_precision": 0.787,
                    "context_recall": 0.926,
                },
                {
                    "faithfulness": (
                        "The Okta answer asserts that 'Google Workspace SSO is included "
                        "on Team as of 2026' and that SCIM 'is a paid add-on'. Retrieved "
                        "context (kb-sso-001, kb-sso-002) says SAML SSO and SCIM are "
                        "Enterprise-only. Those two claims are directly contradicted by "
                        "the passages, not merely missing from them."
                    ),
                    "answer_relevancy": (
                        "Still answers 'do we need Enterprise for Okta?' — just wrongly. "
                        "Relevancy is not truth."
                    ),
                    "context_precision": (
                        "Retrieval did its job. The wrong answer was generated on top of "
                        "the right chunks."
                    ),
                    "context_recall": (
                        "kb-sso-001 was retrieved. Context recall passes; faithfulness "
                        "is 1/5 for the preset and the gate is BLOCKED."
                    ),
                },
            ),
        ],
    },
    {
        "id": "noisy_context",
        "title": "Noisy context",
        "description": (
            "top_k=6 plus noise injection. Gold chunks still appear, so Context "
            "Recall and Faithfulness pass, but the window is packed with unrelated "
            "docs and Context Precision fails 0/5."
        ),
        "config": {"top_k": 6, "prompt_mode": "strict", "noise_injection": True},
        "runs": [
            run(
                1,
                {
                    "faithfulness": 0.928,
                    "answer_relevancy": 0.841,
                    "context_precision": 0.412,
                    "context_recall": 0.971,
                },
                {
                    "faithfulness": (
                        "Strict prompt held. The model ignored SSO and webhook neighbours "
                        "when answering a billing question and stuck to kb-billing-001."
                    ),
                    "answer_relevancy": (
                        "Answers stay on the question. Extra context did not pull the "
                        "generator onto a neighbouring topic."
                    ),
                    "context_precision": (
                        "ContextualPrecisionMetric: of six retrieved chunks, one or two "
                        "are relevant and the rest (API keys, SCIM, CSV sources, "
                        "webhooks-adjacent onboarding) are noise. Rank-aware precision "
                        "collapses. 0/5 against 0.75."
                    ),
                    "context_recall": (
                        "Gold chunks are still in the six-deep window. Recall passes "
                        "because noise was added, not substituted for the truth."
                    ),
                },
            ),
            run(
                2,
                {
                    "faithfulness": 0.911,
                    "answer_relevancy": 0.823,
                    "context_precision": 0.387,
                    "context_recall": 0.954,
                },
                {
                    "faithfulness": (
                        "One sentence borrowed a '24 hour' figure from the API-key "
                        "rotation chunk while answering a refund question; the rest of "
                        "the answer stayed grounded. Score still clears 0.90."
                    ),
                    "answer_relevancy": (
                        "Mild drift on one row (mentions key rotation while asked about "
                        "invites) but the batch mean stays above 0.80."
                    ),
                    "context_precision": (
                        "Irrelevant chunks occupy ranks 2–6 on most questions. Precision "
                        "cannot recover while noise_injection is on."
                    ),
                    "context_recall": (
                        "Required IDs present. This preset is the precision/recall "
                        "tradeoff made visible: raise k, inject noise, watch them split."
                    ),
                },
            ),
            run(
                3,
                {
                    "faithfulness": 0.946,
                    "answer_relevancy": 0.857,
                    "context_precision": 0.441,
                    "context_recall": 0.962,
                },
                {
                    "faithfulness": (
                        "No unsupported claims this run. The generator explicitly skipped "
                        "passages that did not bear on the question."
                    ),
                    "answer_relevancy": (
                        "Outputs match the questions. Noise in the window did not become "
                        "noise in the answer."
                    ),
                    "context_precision": (
                        "Six-chunk lists include kb-apikeys-001 and kb-sso-002 beside "
                        "rate-limit questions. Almost every row has majority-irrelevant "
                        "context."
                    ),
                    "context_recall": (
                        "kb-ratelimit-001 and kb-ratelimit-002 both present for the 429 "
                        "question despite the padding."
                    ),
                },
            ),
            run(
                4,
                {
                    "faithfulness": 0.922,
                    "answer_relevancy": 0.834,
                    "context_precision": 0.365,
                    "context_recall": 0.948,
                },
                {
                    "faithfulness": (
                        "Faithful to the relevant subset of the window. Strict mode is "
                        "doing the work precision is not."
                    ),
                    "answer_relevancy": (
                        "Question coverage holds. A little extra length from having more "
                        "passages to quote, still on-topic."
                    ),
                    "context_precision": (
                        "Worst precision of the five runs. Several questions retrieved "
                        "only one relevant chunk in a six-chunk list."
                    ),
                    "context_recall": (
                        "Recall still clears 0.90. The supporting document is in the "
                        "haystack; precision measures the hay."
                    ),
                },
            ),
            run(
                5,
                {
                    "faithfulness": 0.937,
                    "answer_relevancy": 0.848,
                    "context_precision": 0.398,
                    "context_recall": 0.979,
                },
                {
                    "faithfulness": (
                        "Grounded answers. The 30-day retention and 14-day refund windows "
                        "are cited from the correct chunks, not from neighbouring noise."
                    ),
                    "answer_relevancy": (
                        "All eight answers address the asked questions. Relevancy passes "
                        "5/5 on this preset."
                    ),
                    "context_precision": (
                        "Context Precision fails 0/5. Raising top_k and turning on "
                        "noise_injection is the fastest way to demonstrate a precision "
                        "regression without touching generation."
                    ),
                    "context_recall": (
                        "Highest recall of the run set — the gold chunks have more slots "
                        "to land in. Recall and precision moved in opposite directions, "
                        "which is the point of this preset."
                    ),
                },
            ),
        ],
    },
]


def build() -> dict:
    return {
        "gate_runs": GATE_RUNS,
        "required_passing_runs": REQUIRED_PASSING_RUNS,
        "default_thresholds": DEFAULT_THRESHOLDS,
        "metric_labels": METRIC_LABELS,
        "presets": PRESETS,
    }


def main() -> None:
    payload = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(PRESETS)} presets x {GATE_RUNS} runs to {OUT}")


if __name__ == "__main__":
    main()
