"""End-to-end evaluation harness.

For every (model x scenario):
    1. generate an email with the advanced prompt
    2. score it with the 3 custom metrics (one shared judge call)
Then write the structured outputs the brief asks for and print a comparison table.

Run:  python -m src.evaluate
"""
import csv
import json
import statistics
from datetime import datetime, timezone

import pandas as pd
from tabulate import tabulate

from . import config, generate, metrics


def load_scenarios():
    with open(config.SCENARIOS_PATH, encoding="utf-8") as f:
        return json.load(f)


def run():
    scenarios = load_scenarios()
    config.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()

    generations = []   # full audit trail: email + metric details
    rows = []          # flat per-(model, scenario) score rows

    total = len(config.MODELS) * len(scenarios)
    step = 0
    for display_name, model_id in config.MODELS.items():
        print(f"\n=== Model: {display_name} ({model_id}) ===")
        for sc in scenarios:
            step += 1
            print(f"[{step}/{total}] {sc['id']} ...", flush=True)

            email = generate.generate_email(sc, model_id)
            scores, details = metrics.score_email(sc, email)

            generations.append({
                "model": display_name,
                "model_id": model_id,
                "scenario_id": sc["id"],
                "intent": sc["intent"],
                "tone": sc["tone"],
                "key_facts": sc["key_facts"],
                "reference_email": sc["reference_email"],
                "generated_email": email,
                "scores": scores,
                "details": details,
            })
            rows.append({
                "model": display_name,
                "scenario_id": sc["id"],
                "intent": sc["intent"],
                "tone": sc["tone"],
                "fact_recall": scores["fact_recall"],
                "tone_accuracy": scores["tone_accuracy"],
                "conciseness_fluency": scores["conciseness_fluency"],
                "overall": scores["overall"],
            })
            print(f"      fact={scores['fact_recall']:.0f}  tone={scores['tone_accuracy']:.0f}  "
                  f"concise/fluency={scores['conciseness_fluency']:.0f}  overall={scores['overall']:.0f}")

    finished = datetime.now(timezone.utc).isoformat()
    run_meta = {
        "started_utc": started,
        "finished_utc": finished,
        "models": config.MODELS,
        "judge_model": config.JUDGE_MODEL,
        "gen_temperature": config.GEN_TEMPERATURE,
        "judge_temperature": config.JUDGE_TEMPERATURE,
        "n_scenarios": len(scenarios),
    }

    summary = build_summary(rows, run_meta)
    write_outputs(generations, rows, summary, run_meta)
    print_comparison(summary, rows)
    return summary


def build_summary(rows, run_meta):
    df = pd.DataFrame(rows)
    metric_cols = metrics.METRIC_NAMES + ["overall"]
    per_model = {}
    for model in df["model"].unique():
        sub = df[df["model"] == model]
        per_model[model] = {}
        for col in metric_cols:
            vals = sub[col].tolist()
            per_model[model][col] = {
                "mean": round(statistics.mean(vals), 2),
                "stdev": round(statistics.pstdev(vals), 2),  # population std over the 10
                "min": round(min(vals), 2),
                "max": round(max(vals), 2),
            }

    # Per-metric winner (by mean) for the report.
    winners = {}
    models = list(per_model.keys())
    for col in metric_cols:
        best = max(models, key=lambda m: per_model[m][col]["mean"])
        margin = round(
            per_model[best][col]["mean"]
            - min(per_model[m][col]["mean"] for m in models),
            2,
        )
        winners[col] = {"winner": best, "margin_vs_other": margin}

    return {
        "run_meta": run_meta,
        "metric_definitions": metrics.METRIC_DEFINITIONS,
        "per_model": per_model,
        "winners": winners,
    }


def write_outputs(generations, rows, summary, run_meta):
    rd = config.RESULTS_DIR

    with open(rd / "generations.json", "w", encoding="utf-8") as f:
        json.dump(generations, f, indent=2, ensure_ascii=False)

    # scores.json carries the metric DEFINITIONS + raw rows (brief requirement).
    with open(rd / "scores.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "run_meta": run_meta,
                "metric_definitions": metrics.METRIC_DEFINITIONS,
                "rows": rows,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    with open(rd / "scores.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    with open(rd / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\nWrote: generations.json, scores.json, scores.csv, summary.json -> {rd}")


def print_comparison(summary, rows):
    print("\n================= OVERALL COMPARISON (mean over 10 scenarios) =================")
    table = []
    for model, stats in summary["per_model"].items():
        table.append([
            model,
            f"{stats['fact_recall']['mean']:.1f}",
            f"{stats['tone_accuracy']['mean']:.1f}",
            f"{stats['conciseness_fluency']['mean']:.1f}",
            f"{stats['overall']['mean']:.1f}  (+/-{stats['overall']['stdev']:.1f})",
        ])
    print(tabulate(
        table,
        headers=["Model", "Fact Recall", "Tone Acc.", "Concise/Fluency", "OVERALL"],
        tablefmt="github",
    ))
    print("\nPer-metric winners:")
    for metric, info in summary["winners"].items():
        print(f"  {metric:20s} -> {info['winner']:14s} (margin {info['margin_vs_other']:+.1f})")


if __name__ == "__main__":
    run()
