"""LLM calls with fallback. Owner: D1.

Chain: Brev vLLM (BREV_LLM_URL, skipped if empty, openai client with base_url) -> Gemini -> Groq.
Timeout on each; log which provider answered.
"""
import os
import re
import json
import logging
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("wakil.llm")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

LAST_PROVIDER_USED: Optional[str] = None


def get_last_provider() -> Optional[str]:
    """Return the name of the provider that served the last successful LLM call."""
    return LAST_PROVIDER_USED


def _clean_json_markdown(text: str) -> str:
    """Strip ```json ... ``` markdown fences if present."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


def _call_brev_vllm(prompt: str, json_mode: bool, timeout: float = 20.0) -> str:
    brev_url = os.getenv("BREV_LLM_URL", "").strip()
    if not brev_url:
        raise ValueError("BREV_LLM_URL not set")

    from openai import OpenAI
    # Standard vLLM endpoint
    base_url = brev_url if "/v1" in brev_url else f"{brev_url.rstrip('/')}/v1"
    client = OpenAI(base_url=base_url, api_key="brev-token", timeout=timeout)
    
    # Try fetching available model name or use default
    model_name = os.getenv("BREV_LLM_MODEL", "meta-llama/Meta-Llama-3-8B-Instruct")
    kwargs = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    return _clean_json_markdown(content)


def _call_gemini(prompt: str, json_mode: bool, timeout: float = 25.0) -> str:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set")

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        temperature=0.1,
    )
    if json_mode:
        config.response_mime_type = "application/json"

    # Default to fast flash model
    model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=config,
    )
    content = response.text or ""
    return _clean_json_markdown(content)


def _call_groq(prompt: str, json_mode: bool, timeout: float = 20.0) -> str:
    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GROQ_API_KEY not set")

    from groq import Groq

    client = Groq(api_key=api_key, timeout=timeout)
    model_name = os.getenv("GROQ_LLM_MODEL", "llama-3.3-70b-versatile")
    kwargs = {
        "model": model_name,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    return _clean_json_markdown(content)


def call_llm(prompt: str, json: bool = True) -> str:
    """Call LLM with fallback chain: Brev vLLM -> Gemini -> Groq.
    
    Returns the model's raw text (JSON string if json=True).
    Logs which provider answered.
    """
    global LAST_PROVIDER_USED
    errors = []

    # 1. Brev vLLM (highest priority if configured)
    if os.getenv("BREV_LLM_URL", "").strip():
        try:
            logger.info("Attempting LLM call via Brev vLLM...")
            result = _call_brev_vllm(prompt, json_mode=json)
            LAST_PROVIDER_USED = "brev-vllm"
            logger.info("LLM call succeeded with provider: Brev vLLM")
            return result
        except Exception as e:
            logger.warning(f"Brev vLLM failed: {e}. Falling back to next provider.")
            errors.append(f"brev: {e}")

    # 2. Gemini Flash
    if os.getenv("GEMINI_API_KEY", "").strip():
        try:
            logger.info("Attempting LLM call via Gemini...")
            result = _call_gemini(prompt, json_mode=json)
            LAST_PROVIDER_USED = "gemini"
            logger.info("LLM call succeeded with provider: Gemini")
            return result
        except Exception as e:
            logger.warning(f"Gemini failed: {e}. Falling back to next provider.")
            errors.append(f"gemini: {e}")

    # 3. Groq
    if os.getenv("GROQ_API_KEY", "").strip():
        try:
            logger.info("Attempting LLM call via Groq...")
            result = _call_groq(prompt, json_mode=json)
            LAST_PROVIDER_USED = "groq"
            logger.info("LLM call succeeded with provider: Groq")
            return result
        except Exception as e:
            logger.warning(f"Groq failed: {e}.")
            errors.append(f"groq: {e}")

    # If no provider succeeded
    err_msg = f"All LLM providers failed or no API keys set. Errors: {'; '.join(errors)}"
    logger.error(err_msg)
    raise RuntimeError(err_msg)
