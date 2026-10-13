"""Groq chat-completions client (OpenAI-compatible API) with retry + model fallback."""

import time

import requests

try:
    from . import rag_config as cfg
except ImportError:  # run as a plain script from the scripts/ folder
    import rag_config as cfg


class LLMError(Exception):
    """Raised when the LLM cannot produce an answer (caller should fall back)."""


class LLMNotConfigured(LLMError):
    """GROQ_API_KEY is missing."""


_session = requests.Session()


def _post(model, messages, max_tokens, temperature):
    """POST once, retrying on 429/5xx. Returns the assistant text."""
    headers = {
        "Authorization": f"Bearer {cfg.get_groq_api_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_error = None
    for attempt in range(cfg.GROQ_MAX_RETRIES + 1):
        try:
            resp = _session.post(
                cfg.GROQ_API_URL, headers=headers, json=payload, timeout=cfg.GROQ_TIMEOUT
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = f"network error: {exc.__class__.__name__}"
            time.sleep(min(2 ** attempt, 5))
            continue

        if resp.status_code == 200:
            try:
                text = resp.json()["choices"][0]["message"]["content"] or ""
            except (KeyError, IndexError, ValueError) as exc:
                raise LLMError(f"unexpected response format: {exc}") from exc
            return text.strip()

        if resp.status_code in (401, 403):
            # Never retry bad credentials, and never echo the key.
            raise LLMError("Groq rejected the API key (check GROQ_API_KEY).")

        if resp.status_code == 429 or resp.status_code >= 500:
            try:
                wait = float(resp.headers.get("retry-after", 2 ** attempt))
            except ValueError:
                wait = 2 ** attempt
            last_error = f"HTTP {resp.status_code}"
            if attempt < cfg.GROQ_MAX_RETRIES:
                time.sleep(min(wait, 20))
            continue

        # 400/404 etc: wrong or decommissioned model, bad request.
        detail = ""
        try:
            detail = resp.json().get("error", {}).get("message", "")
        except ValueError:
            pass
        raise LLMError(f"HTTP {resp.status_code} from Groq for model '{model}': {detail}")

    raise LLMError(f"Groq unavailable after retries ({last_error}).")


def generate(system_prompt, user_prompt, history=None, max_tokens=None, temperature=None):
    """Return (answer_text, model_used). Raises LLMError if every model fails.

    history: optional prior turns [{'role': 'user'|'assistant', 'content': str}].
    """
    if not cfg.get_groq_api_key():
        raise LLMNotConfigured("GROQ_API_KEY is not set.")

    messages = (
        [{"role": "system", "content": system_prompt}]
        + list(history or [])
        + [{"role": "user", "content": user_prompt}]
    )
    max_tokens = max_tokens or cfg.LLM_MAX_TOKENS
    temperature = cfg.LLM_TEMPERATURE if temperature is None else temperature

    models = [cfg.GROQ_MODEL]
    if cfg.GROQ_FALLBACK_MODEL and cfg.GROQ_FALLBACK_MODEL != cfg.GROQ_MODEL:
        models.append(cfg.GROQ_FALLBACK_MODEL)

    errors = []
    for model in models:
        try:
            text = _post(model, messages, max_tokens, temperature)
        except LLMError as exc:
            errors.append(str(exc))
            if "API key" in str(exc):
                break  # fallback model will not help
            continue
        if text:
            return text, model
        errors.append(f"empty answer from {model}")

    raise LLMError("; ".join(errors))
