"""Email generation: turn a scenario into an email with a given model."""
from . import config, llm_client, prompts


def generate_email(scenario: dict, model_id: str) -> str:
    messages = prompts.build_messages(
        scenario["intent"], scenario["key_facts"], scenario["tone"]
    )
    email = llm_client.chat(
        messages, model_id, config.GEN_TEMPERATURE, config.GEN_MAX_TOKENS
    )
    return email.strip()
