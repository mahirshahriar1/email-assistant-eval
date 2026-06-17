"""Thin Groq client wrapper.

Responsibilities:
  * lazy, single client construction
  * `chat()`        -> free-text completion (email generation)
  * `json_chat()`   -> JSON-mode completion, parsed to a dict (the LLM judge)
  * exponential backoff that absorbs free-tier 429 (rate-limit) responses
  * a fixed inter-call sleep so we stay under the requests/min ceiling
"""
import json
import re
import time

import groq

from . import config

_client = None


def client() -> groq.Groq:
    global _client
    if _client is None:
        if not config.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
            )
        _client = groq.Groq(api_key=config.GROQ_API_KEY)
    return _client


def _retry_after_seconds(err, attempt) -> float:
    """Honour a Retry-After header if Groq sends one; else exponential backoff."""
    try:
        ra = err.response.headers.get("retry-after")
        if ra is not None:
            return float(ra) + 1.0
    except Exception:
        pass
    return config.BACKOFF_BASE * (2 ** attempt)


def _create(messages, model, temperature, max_tokens, json_mode=False, throttle=True) -> str:
    kwargs = dict(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    last_err = None
    for attempt in range(config.MAX_RETRIES):
        try:
            resp = client().chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            if throttle:
                time.sleep(config.INTER_CALL_SLEEP)  # batch hygiene; skipped for interactive
            return content
        except groq.RateLimitError as e:
            last_err = e
            wait = _retry_after_seconds(e, attempt)
            print(f"  [rate-limit] {model}: attempt {attempt + 1}/{config.MAX_RETRIES}, "
                  f"waiting {wait:.0f}s")
            time.sleep(wait)
        except (groq.APIConnectionError, groq.APITimeoutError, groq.InternalServerError) as e:
            last_err = e
            wait = config.BACKOFF_BASE * (2 ** attempt)
            print(f"  [transient] {model}: {type(e).__name__}, waiting {wait:.0f}s")
            time.sleep(wait)
    raise RuntimeError(f"Groq call to {model} failed after {config.MAX_RETRIES} retries: {last_err}")


def chat(messages, model, temperature, max_tokens, throttle=True) -> str:
    """Free-text completion. Pass throttle=False for low-latency interactive calls."""
    return _create(messages, model, temperature, max_tokens, json_mode=False, throttle=throttle)


def json_chat(messages, model, temperature, max_tokens) -> dict:
    """JSON-mode completion, returned as a parsed dict.

    JSON mode makes the model emit a single JSON object, but we still defend against a
    stray code-fence or prose wrapper before parsing.
    """
    raw = _create(messages, model, temperature, max_tokens, json_mode=True)
    return _parse_json(raw)


def _parse_json(raw: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Extract the first {...} block as a fallback.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise
