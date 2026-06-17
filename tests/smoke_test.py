"""Cheap end-to-end smoke test: 1 scenario x 1 model.

Validates the whole pipeline (prompt -> generation -> judge -> 3 metrics) with a single
pair of API calls before committing to the full 20-generation run.

Run:  python -m tests.smoke_test
"""
from src import config, generate, metrics
from src.evaluate import load_scenarios


def main():
    scenarios = load_scenarios()
    sc = scenarios[0]
    model_id = config.MODELS["llama-3.3-70b"]

    print(f"Scenario: {sc['id']}  |  Model: {model_id}\n")
    email = generate.generate_email(sc, model_id)
    assert email and len(email) > 40, "Generated email looks empty/too short"
    print("--- GENERATED EMAIL ---")
    print(email)

    scores, details = metrics.score_email(sc, email)
    print("\n--- SCORES ---")
    for k, v in scores.items():
        print(f"  {k:20s}: {v}")

    for name in metrics.METRIC_NAMES:
        assert 0.0 <= scores[name] <= 100.0, f"{name} out of range: {scores[name]}"
    print("\nSmoke test passed: pipeline works end-to-end.")


if __name__ == "__main__":
    main()
