"""Score a RAG system on the four metrics that matter, using Ragas.

Ragas works at the DATASET level: you hand it a batch of rows and it returns
one score per metric across the whole batch. That is the shape you want once
you have more than a handful of examples and you are asking "did this change
make the feature better or worse overall?"

Run it:

    export OPENAI_API_KEY=sk-...
    python ragas_eval.py

Every metric below is computed by an LLM judge, so the scores move a little
between runs on identical input. That is normal, not a bug, and it is exactly
why the CI gate in tests/test_rag_gate.py gates on a repeated-run pass rate
instead of a single verdict.
"""

import os

from datasets import Dataset
from ragas import evaluate
from ragas.metrics import (
    answer_relevancy,
    context_precision,
    context_recall,
    faithfulness,
)

# Ragas 0.2+ column names, and what each one has to contain:
#   user_input          the question that was asked
#   response            what your RAG pipeline actually answered
#   retrieved_contexts  the chunks your retriever returned for that question
#   reference           the human-written ground-truth answer
#
# Faithfulness and answer relevancy only need the generation side.
# Context precision and context recall need `reference` too, because they
# compare what was retrieved against what the correct answer required.
EXAMPLES = {
    "user_input": [
        "When does my invoice actually get sent out?",
        "How many API calls can I make on the Team plan?",
        "Can I get a refund if I cancel three weeks in?",
    ],
    "response": [
        (
            "Meridian bills on the same calendar day you subscribed. The invoice "
            "is generated at 00:00 UTC on that day and emailed to your billing "
            "contact."
        ),
        (
            "The Team plan allows 600 requests per minute. The limit is measured "
            "per workspace over a sliding 60 second window, not per API key."
        ),
        (
            "A full refund is available within 14 days of your first paid invoice. "
            "Three weeks in, a monthly renewal is outside that window, so it is not "
            "refundable, though annual plans can still get a prorated refund within "
            "30 days."
        ),
    ],
    "retrieved_contexts": [
        [
            "Billing cycles and invoices: Meridian bills monthly on the calendar "
            "day you subscribed. Invoices are generated at 00:00 UTC on the billing "
            "day and emailed to the workspace billing contact.",
            "Annual plans are billed once for twelve months upfront and receive a "
            "15 percent discount against the monthly rate.",
        ],
        [
            "API rate limits by plan: Free allows 60 requests per minute, Team "
            "allows 600 requests per minute, and Enterprise allows 6000 requests "
            "per minute. Limits apply per workspace, not per API key, and are "
            "measured over a sliding 60 second window.",
        ],
        [
            "Refund policy: a full refund is available within 14 days of the first "
            "paid invoice. Annual plans are eligible for a prorated refund within "
            "30 days. Monthly renewals are not refundable after 14 days.",
            "Requesting a refund: email billing@meridian.example with the invoice "
            "number. Approved refunds are processed in 5 to 7 business days.",
        ],
    ],
    "reference": [
        (
            "Invoices are generated at 00:00 UTC on your monthly billing day, which "
            "is the calendar day you subscribed, and emailed to the billing contact."
        ),
        (
            "The Team plan allows 600 requests per minute, applied per workspace "
            "over a sliding 60 second window."
        ),
        (
            "A monthly renewal is not refundable after 14 days, so a cancellation at "
            "three weeks does not qualify. Annual plans remain eligible for a "
            "prorated refund within 30 days."
        ),
    ],
}

# The only four metrics an app builder needs. Two watch retrieval
# (context precision, context recall), two watch generation
# (faithfulness, answer relevancy).
METRICS = [faithfulness, answer_relevancy, context_precision, context_recall]


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not set. Every metric here is scored by an LLM "
            "judge, so the key is required.\n\n    export OPENAI_API_KEY=sk-..."
        )

    dataset = Dataset.from_dict(EXAMPLES)
    result = evaluate(dataset=dataset, metrics=METRICS)

    # to_pandas() gives one row per example and one column per metric, so you
    # can see which specific question dragged a score down instead of only
    # seeing the batch average.
    per_row = result.to_pandas()

    print(f"\nScored {len(per_row)} examples on {len(METRICS)} metrics\n")
    print(f"{'metric':<22}{'mean':>8}{'min':>8}")
    print("-" * 38)
    for metric in METRICS:
        column = per_row[metric.name]
        print(f"{metric.name:<22}{column.mean():>8.3f}{column.min():>8.3f}")
    print()

    # The minimum column is the one worth reading. A batch mean of 0.90 with a
    # single row at 0.20 is one broken question, not a uniformly decent system.
    worst = per_row[[m.name for m in METRICS]].min(axis=1).idxmin()
    print(f"Weakest example (row {worst}): {per_row.loc[worst, 'user_input']}\n")


if __name__ == "__main__":
    main()
