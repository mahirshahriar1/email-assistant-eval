"""Central configuration: models, reproducibility params, rate-limit hygiene, paths.

Every knob that affects results lives here and is logged into the output files, so a
run is fully auditable and reproducible.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# --- Candidate models under comparison -------------------------------------------------
# Apples-to-apples by design: both are large, open-weight, instruction-tuned flagships
# served on the SAME provider/infra (Groq) with a 131K context window and on the free
# tier. A score gap is therefore attributable to the *model*, not to vendor, price, or
# deployment differences. Keys are short display names; values are Groq model IDs.
MODELS = {
    "llama-3.3-70b": "llama-3.3-70b-versatile",   # Meta
    "gpt-oss-120b": "openai/gpt-oss-120b",         # OpenAI open-weight
}

# --- LLM-as-a-judge --------------------------------------------------------------------
# ONE fixed, neutral judge is used to score BOTH candidates. Using a single judge for
# both removes the obvious confound where a model rates its own output favourably
# (self-preference bias). Its known limitations are documented in the report.
JUDGE_MODEL = "llama-3.3-70b-versatile"

# --- Reproducibility -------------------------------------------------------------------
GEN_TEMPERATURE = 0.3      # low but non-zero: stable, professional, not robotic
GEN_MAX_TOKENS = 800
JUDGE_TEMPERATURE = 0.0    # deterministic scoring
JUDGE_MAX_TOKENS = 900

# --- Free-tier rate-limit hygiene ------------------------------------------------------
# Free tier is ~30 RPM and 8-12K TPM per model, so calls run sequentially with a short
# inter-call sleep, and 429s are absorbed by exponential backoff.
INTER_CALL_SLEEP = 4.0     # seconds between successful calls
MAX_RETRIES = 6
BACKOFF_BASE = 4.0         # backoff = BACKOFF_BASE * 2**attempt (4,8,16,32,64,128s)

# --- Reference cost / throughput (Groq published, for the production recommendation) ---
# $ per 1M tokens (input/output), and tokens/sec.
MODEL_ECONOMICS = {
    "llama-3.3-70b": {"in_per_mtok": 0.59, "out_per_mtok": 0.79, "tps": 280},
    "gpt-oss-120b": {"in_per_mtok": 0.15, "out_per_mtok": 0.60, "tps": 500},
}

# --- Paths -----------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RESULTS_DIR = ROOT / "results"
SCENARIOS_PATH = DATA_DIR / "scenarios.json"
