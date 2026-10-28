"""
Wrapper around the Google GenAI SDK for the P16 contextual-detection engine.
Targets gemini-3.5-flash-lite with robust automatic retry and rate-limit backoff.
"""

import json
import os
import re
import sys
import time

CANDIDATE_MODELS = [
    os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite"),
    "gemini-3.5-flash-lite",
]


def _extract_retry_delay(err_msg: str) -> float:
    """Extracts suggested retry delay in seconds from Gemini rate-limit error message."""
    match = re.search(r"Please retry in\s+(\d+\.?\d*)s", err_msg)
    if match:
        return float(match.group(1)) + 1.5
    match2 = re.search(r"retryDelay['\"]:\s*['\"](\d+)s", err_msg)
    if match2:
        return float(match2.group(1)) + 1.5
    return 30.0


def call_gemini(prompt: str, model_name: str | None = None, temperature: float = 0.2, max_retries: int = 5) -> str:
    """Send a prompt to Gemini with automatic rate-limit backoff and retry."""
    if not os.environ.get("GEMINI_API_KEY"):
        for env_path in [
            os.path.join(os.path.dirname(__file__), "..", ".env"),
            os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        ]:
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GEMINI_API_KEY="):
                            os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not set. Please add it to .env or run: export GEMINI_API_KEY=...")

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=api_key)

    chosen_model = model_name or os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
    cfg = types.GenerateContentConfig(temperature=temperature) if temperature is not None else None

    last_err = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=chosen_model,
                contents=prompt,
                config=cfg,
            )
            if response and response.text:
                return response.text
        except Exception as e:
            last_err = e
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                delay = _extract_retry_delay(err_str)
                print(f"[Gemini 429 Quota] Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...", file=sys.stderr)
                time.sleep(delay)
                continue
            else:
                # If non-quota error, retry once after short backoff
                time.sleep(2.0)
                continue

    raise RuntimeError(f"All Gemini attempts failed for model {chosen_model}. Last error: {last_err}")


def call_gemini_json(prompt: str, model_name: str | None = None, temperature: float = 0.2) -> list:
    """
    Call Gemini and parse the response as a JSON list of findings.
    Strips markdown code fences if the model wraps its output in them.
    """
    raw = call_gemini(prompt, model_name=model_name, temperature=temperature)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        if len(parts) >= 2:
            cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
    cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
        return [{"parse_error": True, "raw_response": raw}]
