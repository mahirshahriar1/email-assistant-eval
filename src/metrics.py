"""Three custom evaluation metrics for an email-generation assistant.

Design principle: match the *measurement technique* to the *nature of the quality*.
  - Some quality is objective and verifiable  -> measure it (Python / structured LLM check).
  - Some quality is subjective and holistic   -> have a calibrated LLM judge rate it.

  METRIC 1  Fact Recall          (objective)            -> structured LLM check, scored in Python
  METRIC 2  Tone Accuracy        (subjective)           -> LLM-as-judge rubric
  METRIC 3  Conciseness & Fluency(objective + subjective)-> Python length analysis + LLM fluency

All three return a 0-100 score plus a details dict (for auditability in the results file).

Efficiency note: the three metrics that need a model share ONE judge call per
(scenario, email). One structured call returns fact presence, a tone score, and a fluency
score together. This keeps us well under the free-tier token budget while keeping each
metric's definition and scoring logic cleanly separated below.
"""
import re

from . import config, llm_client

# ---------------------------------------------------------------------------------------
# Pure-Python text helpers
# ---------------------------------------------------------------------------------------

def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _sentences(text: str):
    return [s.strip() for s in re.split(r"[.!?\n]+", text) if s.strip()]


def _avg_sentence_length(text: str) -> float:
    sents = _sentences(text)
    if not sents:
        return 0.0
    return _word_count(text) / len(sents)


# ---------------------------------------------------------------------------------------
# Shared LLM judge (one structured call powers metrics 1, 2, and the fluency half of 3)
# ---------------------------------------------------------------------------------------

_JUDGE_SYSTEM = (
    "You are a meticulous, impartial evaluator of professional emails. "
    "You follow the rubric exactly and respond ONLY with a single JSON object."
)


def _judge_messages(scenario: dict, email: str):
    facts = scenario["key_facts"]
    facts_block = "\n".join(f'- "{f}"' for f in facts)
    instructions = f"""Evaluate the EMAIL below against the brief.

REQUESTED TONE: {scenario['tone']}

KEY FACTS that were required to appear in the email:
{facts_block}

EMAIL TO EVALUATE:
\"\"\"
{email}
\"\"\"

Return a JSON object with EXACTLY this shape:
{{
  "fact_assessments": [
    {{"fact": "<repeat the fact verbatim>", "present": true|false}}
    // one entry per required fact, in the same order
  ],
  "tone_score_1_5": <integer 1-5>,        // 5 = tone matches the requested tone perfectly
  "tone_rationale": "<one short sentence>",
  "fluency_score_1_5": <integer 1-5>,     // 5 = flawless grammar, natural, well-written
  "fluency_rationale": "<one short sentence>"
}}

Scoring guidance:
- A fact is "present" only if its meaning is clearly conveyed (paraphrase is fine; a missing
  number/date/name is NOT present).
- tone_score: 5 perfect, 4 good with minor drift, 3 acceptable, 2 noticeably off, 1 wrong tone.
- fluency_score: judge grammar, clarity, and natural phrasing only (not facts or tone)."""
    return [
        {"role": "system", "content": _JUDGE_SYSTEM},
        {"role": "user", "content": instructions},
    ]


def judge(scenario: dict, email: str) -> dict:
    """One structured judge call shared by the metrics below."""
    return llm_client.json_chat(
        _judge_messages(scenario, email),
        config.JUDGE_MODEL,
        config.JUDGE_TEMPERATURE,
        config.JUDGE_MAX_TOKENS,
    )


# ---------------------------------------------------------------------------------------
# METRIC 1 - Fact Recall
# ---------------------------------------------------------------------------------------
# WHY IT MATTERS: an email that drops a required fact (the price, the date, the order
#   number) is a functional failure no matter how nicely it reads. This is the single
#   most important correctness metric for this task.
# TECHNIQUE: objective, so we don't ask the LLM for a vibe score - we ask it a verifiable
#   yes/no per fact and compute the score deterministically in Python.
# LOGIC: score = (facts marked present / total facts) * 100.
def fact_recall(scenario: dict, email: str, judge_payload: dict):
    facts = scenario["key_facts"]
    assessments = judge_payload.get("fact_assessments", [])
    present = sum(1 for a in assessments if a.get("present"))
    total = len(facts)
    score = 100.0 * present / total if total else 0.0
    return score, {
        "facts_total": total,
        "facts_present": present,
        "assessments": assessments,
    }


# ---------------------------------------------------------------------------------------
# METRIC 2 - Tone Accuracy
# ---------------------------------------------------------------------------------------
# WHY IT MATTERS: tone is the difference between an apology that lands and one that makes
#   things worse. It is the core "did you follow the style instruction" metric.
# TECHNIQUE: tone is inherently subjective/holistic, so a calibrated LLM judge on a 1-5
#   rubric is the right tool (a keyword heuristic cannot tell "warm" from "curt").
# LOGIC: rubric score (1-5) mapped linearly to 0-100 (x20).
def tone_accuracy(scenario: dict, email: str, judge_payload: dict):
    raw = int(judge_payload.get("tone_score_1_5", 0) or 0)
    raw = max(0, min(5, raw))
    score = 20.0 * raw
    return score, {
        "tone_score_1_5": raw,
        "requested_tone": scenario["tone"],
        "rationale": judge_payload.get("tone_rationale", ""),
    }


# ---------------------------------------------------------------------------------------
# METRIC 3 - Conciseness & Fluency
# ---------------------------------------------------------------------------------------
# WHY IT MATTERS: a correct, on-tone email still fails if it is bloated or clumsy. Busy
#   readers reward brevity and clean writing.
# TECHNIQUE: a deliberate hybrid -
#   * CONCISENESS is objective -> measured in pure Python by comparing length to the human
#     reference email (the "ideal" length for that brief) plus a sentence-length sanity check.
#   * FLUENCY is subjective -> scored by the LLM judge (grammar / natural phrasing).
# LOGIC: final = 0.5 * length_score(Python) + 0.5 * fluency_score(LLM).
def conciseness_fluency(scenario: dict, email: str, judge_payload: dict):
    ref_wc = max(1, _word_count(scenario["reference_email"]))
    gen_wc = _word_count(email)
    ratio = gen_wc / ref_wc

    # Length score: full marks when within a sensible band around the reference length,
    # tapering to 0 for very terse or very bloated emails.
    length_score = _length_band_score(ratio)

    # Sentence-length sanity: gently penalise walls of text (very long avg sentences).
    avg_sent = _avg_sentence_length(email)
    if avg_sent > 30:
        length_score *= 0.85
    elif avg_sent > 25:
        length_score *= 0.93

    fluency_raw = int(judge_payload.get("fluency_score_1_5", 0) or 0)
    fluency_raw = max(0, min(5, fluency_raw))
    fluency_score = 20.0 * fluency_raw

    final = 0.5 * length_score + 0.5 * fluency_score
    return final, {
        "reference_words": ref_wc,
        "generated_words": gen_wc,
        "length_ratio": round(ratio, 3),
        "length_score": round(length_score, 1),
        "avg_sentence_length": round(avg_sent, 1),
        "fluency_score_1_5": fluency_raw,
        "fluency_rationale": judge_payload.get("fluency_rationale", ""),
    }


def _length_band_score(ratio: float) -> float:
    """0-100 score for how close the email length is to the reference length.

    Ideal band 0.80-1.25x -> 100. Acceptable 0.60-1.50x -> 70-100 (linear).
    Outside that, taper to 0 at <=0.30x (too terse) or >=2.50x (too bloated).
    """
    if 0.80 <= ratio <= 1.25:
        return 100.0
    if 0.60 <= ratio < 0.80:
        return 70.0 + (ratio - 0.60) / (0.80 - 0.60) * 30.0
    if 1.25 < ratio <= 1.50:
        return 100.0 - (ratio - 1.25) / (1.50 - 1.25) * 30.0
    if 0.30 <= ratio < 0.60:
        return max(0.0, (ratio - 0.30) / (0.60 - 0.30) * 70.0)
    if 1.50 < ratio <= 2.50:
        return max(0.0, 70.0 - (ratio - 1.50) / (2.50 - 1.50) * 70.0)
    return 0.0


# ---------------------------------------------------------------------------------------
# Orchestration helper: run all three metrics for one (scenario, email)
# ---------------------------------------------------------------------------------------

METRIC_NAMES = ["fact_recall", "tone_accuracy", "conciseness_fluency"]

METRIC_DEFINITIONS = {
    "fact_recall": {
        "focus": "Fact Recall / Specificity",
        "technique": "Structured LLM check (per-fact yes/no) scored deterministically in Python",
        "logic": "score = (facts marked present / total required facts) * 100",
        "why": "Dropping a required fact is a functional failure regardless of writing quality.",
    },
    "tone_accuracy": {
        "focus": "Tone Accuracy",
        "technique": "LLM-as-judge, 1-5 rubric",
        "logic": "rubric score (1-5) * 20 -> 0-100",
        "why": "Tone is subjective and holistic; a keyword heuristic cannot judge it.",
    },
    "conciseness_fluency": {
        "focus": "Conciseness & Grammar/Fluency",
        "technique": "Hybrid: pure-Python length analysis vs the human reference + LLM fluency rubric",
        "logic": "0.5 * length_band_score(len/ref_len, Python) + 0.5 * (fluency 1-5 * 20, LLM)",
        "why": "A correct, on-tone email still fails if it is bloated or clumsy.",
    },
}


def score_email(scenario: dict, email: str):
    """Run the shared judge call + all three metrics. Returns (scores, details)."""
    payload = judge(scenario, email)
    fr, fr_d = fact_recall(scenario, email, payload)
    ta, ta_d = tone_accuracy(scenario, email, payload)
    cf, cf_d = conciseness_fluency(scenario, email, payload)
    scores = {
        "fact_recall": round(fr, 2),
        "tone_accuracy": round(ta, 2),
        "conciseness_fluency": round(cf, 2),
    }
    scores["overall"] = round(sum(scores.values()) / 3.0, 2)
    details = {"fact_recall": fr_d, "tone_accuracy": ta_d, "conciseness_fluency": cf_d}
    return scores, details
