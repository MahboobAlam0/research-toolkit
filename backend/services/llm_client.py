# ─── backend/services/llm_client.py ───────────────────────────────────────────
"""
Thin wrapper around Groq's chat completion API.
Model: llama-3.3-70b-versatile  — fast, free tier available.
Set GROQ_API_KEY in your .env file.
"""
import os
import httpx
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL   = "llama-3.3-70b-versatile"


def _get_key() -> str:
    key = os.getenv("GROQ_API_KEY", "")
    if not key:
        raise EnvironmentError("GROQ_API_KEY not set in environment / .env file.")
    return key


async def chat_completion(
    messages: List[Dict[str, str]],
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> str:
    """
    Send a list of messages to Groq and return the assistant reply as a string.

    Args:
        messages: List of {"role": "...", "content": "..."} dicts.
        temperature: Sampling temperature (lower = more focused).
        max_tokens: Max response tokens.

    Returns:
        Assistant reply text.
    """
    headers = {
        "Authorization": f"Bearer {_get_key()}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(GROQ_API_URL, headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
        return data["choices"][0]["message"]["content"].strip()
