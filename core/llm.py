"""LLM calls with fallback.  Owner: D1.

Chain: Brev vLLM (BREV_LLM_URL, skipped if empty, openai client with base_url) -> Gemini -> Groq.
Timeout on each; log which provider answered.
"""


def call_llm(prompt, json=True):
    """Return the model's raw text."""
    # STUB
    return "{}"
