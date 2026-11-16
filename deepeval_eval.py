"""Score a single RAG interaction on the same four metrics, using DeepEval.

Where Ragas scores a dataset, DeepEval scores a TEST CASE. That is the shape
you want when you are asserting on one scenario at a time inside a normal
pytest run, rather than scoring a batch offline.

Run it:

    export OPENAI_API_KEY=sk-...
    python deepeval_eval.py

The four metrics map one-to-one onto the Ragas four:

    FaithfulnessMetric        -> faithfulness
    AnswerRelevancyMetric     -> answer_relevancy
    ContextualPrecisionMetric -> context_precision
    ContextualRecallMetric    -> context_recall

Each metric returns a score in [0, 1] plus a natural-language reason, which is
the part worth reading when a gate fails. A score tells you something broke.
The reason tells you which claim was unsupported or which chunk was missing.
"""

import os

from deepeval.metrics import (
    AnswerRelevancyMetric,
    ContextualPrecisionMetric,
    ContextualRecallMetric,
    FaithfulnessMetric,
)
from deepeval.test_case import LLMTestCase

# An LLMTestCase carries the same four pieces of information a Ragas row does:
#   input            the question that was asked
#   actual_output    what your RAG pipeline answered
#   retrieval_context the chunks your retriever returned
#   expected_output  the human-written ground-truth answer
#
# Faithfulness and answer relevancy do not need expected_output. The two
# contextual metrics do, because they judge retrieval against the answer the
# question was supposed to get.
TEST_CASE = LLMTestCase(
    input="What do I do when the API starts returning 429?",
    actual_output=(
        "A 429 means you exceeded your plan's rate limit. Read the Retry-After "
        "header, which gives the number of seconds to wait, and retry with "
        "exponential backoff. You can also watch X-RateLimit-Remaining to back "
        "off before you hit the ceiling. Note that bulk endpoints count as ten "
        "requests each."
    ),
    expected_output=(
        "Respect the Retry-After header on the 429 response, back off "
        "exponentially, and monitor X-RateLimit-Remaining and X-RateLimit-Reset "
        "to avoid hitting the limit at all. Bulk endpoints count as ten requests "
        "against the limit."
    ),
    retrieval_context=[
        (
            "Handling 429 responses: a 429 response includes a Retry-After header "
            "giving the number of seconds to wait before retrying. Clients should "
            "retry with exponential backoff. Every response also carries "
            "X-RateLimit-Remaining and X-RateLimit-Reset headers."
        ),
        (
            "Bulk endpoints count as ten requests against your rate limit rather "
            "than one, because each call fans out server side."
        ),
        (
            "API rate limits by plan: Free allows 60 requests per minute, Team "
            "allows 600 requests per minute, and Enterprise allows 6000 requests "
            "per minute."
        ),
    ],
)

# threshold= is DeepEval's own per-metric pass mark, and it is what makes
# metric.is_successful() meaningful. These mirror the constants in
# tests/test_rag_gate.py: faithfulness and retrieval recall are held higher,
# relevancy and precision get a little more room.
#
# Built inside a function rather than at import time on purpose: DeepEval
# resolves its judge model in the metric constructor, so building these at
# module scope turns a missing API key into an import error.
def build_metrics() -> list:
    return [
        FaithfulnessMetric(threshold=0.90, include_reason=True),
        AnswerRelevancyMetric(threshold=0.80, include_reason=True),
        ContextualPrecisionMetric(threshold=0.75, include_reason=True),
        ContextualRecallMetric(threshold=0.90, include_reason=True),
    ]


def main() -> None:
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit(
            "OPENAI_API_KEY is not set. Every metric here is scored by an LLM "
            "judge, so the key is required.\n\n    export OPENAI_API_KEY=sk-..."
        )

    print(f"\nQuestion: {TEST_CASE.input}\n")

    for metric in build_metrics():
        # measure() runs the LLM judge synchronously and populates
        # metric.score, metric.reason, and metric.is_successful().
        metric.measure(TEST_CASE)
        verdict = "PASS" if metric.is_successful() else "FAIL"
        print(f"{metric.__class__.__name__}")
        print(f"  score  : {metric.score:.3f} (threshold {metric.threshold:.2f}) {verdict}")
        print(f"  reason : {metric.reason}\n")


if __name__ == "__main__":
    main()
