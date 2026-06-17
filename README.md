# Email Generation Assistant + Custom Evaluation

A working prototype that generates professional emails from structured input
(**Intent + Key Facts + Tone**) using an LLM, plus a custom evaluation harness that
scores output quality with **three bespoke metrics** and runs a head-to-head
**model comparison**.

Built for the AI Engineer assessment. Provider: **Groq** (free tier). Models compared:
`llama-3.3-70b-versatile` (Meta) vs `openai/gpt-oss-120b` (OpenAI open-weight).

---

## 1. What it does

- **`src/generate.py`** — turns a scenario into a polished email using an advanced prompt.
- **`src/metrics.py`** — three custom metrics score every generated email 0-100.
- **`src/evaluate.py`** — runs all 10 scenarios against both models, scores them, and writes
  structured results + a comparison table.

---

## 2. Setup

```bash
pip install -r requirements.txt
cp .env.example .env          # then paste your Groq key into .env
# GROQ_API_KEY=gsk_...
```

Get a free key at <https://console.groq.com/keys>.

## 3. Run

```bash
python -m tests.smoke_test    # cheap 1-scenario sanity check (2 API calls)
python -m src.evaluate        # full run: 10 scenarios x 2 models -> results/
```

Outputs land in `results/`:

| File | Contents |
|---|---|
| `generations.json` | Every generated email + per-metric details (full audit trail) |
| `scores.json` | Metric **definitions/logic** + raw per-scenario scores |
| `scores.csv` | Flat scores table (10 x 2 rows) |
| `summary.json` | Per-model means, std, min/max + per-metric winners |

---

## 4. The advanced prompting technique

The prompt (`src/prompts.py`) combines **three** techniques, and the *same* template is sent
to both models so the comparison isolates the model:

1. **Role-Playing** — the system prompt casts the model as an *expert executive communications
   assistant*, which lifts register, structure, and professionalism.
2. **Few-Shot** — two compact input→email exemplars (a friendly scheduling email and an
   empathetic apology) teach the output format and the "include every fact, match the tone"
   contract by demonstration.
3. **Chain-of-Thought (hidden)** — the model is told to *plan silently* (recipient & goal →
   check off each key fact → calibrate tone → structure) and then output **only** the final
   email. Hidden planning improves fact coverage and structure; suppressing the visible
   reasoning keeps output clean for both a reasoning model (gpt-oss) and a non-reasoning one
   (llama).

---

## 5. The three custom metrics

Design principle: **match the measurement technique to the nature of the quality.**

| # | Metric | Focus | Technique | Logic |
|---|--------|-------|-----------|-------|
| 1 | **Fact Recall** | Fact Recall / Specificity | Structured LLM check (per-fact yes/no), scored in Python | `present / total * 100` |
| 2 | **Tone Accuracy** | Tone Accuracy | LLM-as-judge, 1-5 rubric | `rubric * 20` |
| 3 | **Conciseness & Fluency** | Conciseness + Grammar/Fluency | **Hybrid**: pure-Python length analysis vs the human reference **+** LLM fluency rubric | `0.5*length_band(Python) + 0.5*(fluency*20)` |

- **Fact Recall** is objective, so it's measured with a verifiable per-fact check, not a vibe score.
- **Tone** is subjective, so a calibrated LLM judge is the right tool.
- **Conciseness & Fluency** is deliberately split: conciseness is objective (Python length ratio
  vs the ideal human-written reference) and fluency is subjective (LLM rubric).

**Judge integrity:** one fixed neutral judge (`llama-3.3-70b-versatile`) scores **both**
candidates at `temperature=0`, which removes self-preference bias and makes scoring deterministic.
Efficiency: the parts that need a model share **one** structured judge call per email.

The full results and analysis live in **[`report/REPORT.md`](report/REPORT.md)**.

---

## 6. Project layout

```
src/config.py      models, reproducibility params, rate-limit settings, paths
src/llm_client.py  Groq wrapper: retry/backoff on 429, JSON mode, inter-call sleep
src/prompts.py     advanced prompt (role-play + few-shot + CoT)
src/generate.py    generate_email(scenario, model)
src/metrics.py     the 3 custom metrics + shared judge
src/evaluate.py    orchestrator + results writers
data/scenarios.json  10 scenarios + human reference emails
results/             generated outputs (committed - they are a deliverable)
report/REPORT.md     final report (prompt, metric defs, raw data, analysis)
tests/smoke_test.py  cheap pipeline check
```

## 7. Notes & limitations

- **n = 10** is a small sample — the report reports per-metric spread and avoids over-claiming.
- **LLM-as-judge** has known biases (verbosity, self-consistency); the single-neutral-judge +
  `temperature=0` design mitigates, but does not eliminate, them.
- Free-tier rate limits (≈30 RPM / 8-12K TPM) mean calls run sequentially with backoff.
