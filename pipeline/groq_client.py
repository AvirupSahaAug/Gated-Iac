"""
Wrapper around Groq API SDK for the P16 contextual-detection engine.
Allows benchmarking GateIaC across Groq LPUs with models such as qwen/qwen3.8-27b.
"""

import json
import os
import re
from groq import Groq

DEFAULT_GROQ_MODELS = [
    os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b"),
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
]


def call_groq(prompt: str, model_name: str | None = None, temperature: float = 0.2) -> str:
    """Send a prompt to Groq API with model failover."""
    if not os.environ.get("GROQ_API_KEY"):
        for env_path in [
            os.path.join(os.path.dirname(__file__), "..", ".env"),
            os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
        ]:
            if os.path.exists(env_path):
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("GROQ_API_KEY="):
                            os.environ["GROQ_API_KEY"] = line.split("=", 1)[1].strip().strip('"').strip("'")
                            break

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY is not set. Add it to .env or export GROQ_API_KEY=...")

    client = Groq(api_key=api_key)

    models_to_try = [model_name] if model_name else []
    for m in DEFAULT_GROQ_MODELS:
        if m and m not in models_to_try:
            models_to_try.append(m)

    last_err = None
    for m in models_to_try:
        try:
            response = client.chat.completions.create(
                model=m,
                messages=[
                    {"role": "system", "content": "You are a cloud security expert analyzing Infrastructure as Code. Always reply strictly with JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
            )
            if response and response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"All Groq models failed. Last error: {last_err}")


def call_groq_json(prompt: str, model_name: str | None = None, temperature: float = 0.2) -> list:
    """
    Call Groq and parse the response as a JSON list of findings.
    Strips markdown code fences if wrapped.
    """
    raw = call_groq(prompt, model_name=model_name, temperature=temperature)
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

