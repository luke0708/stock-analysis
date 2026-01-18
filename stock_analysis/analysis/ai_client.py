"""
AI client helpers for DeepSeek.
"""
from __future__ import annotations

import logging
import os
from typing import Tuple

import requests


def get_deepseek_key() -> Tuple[str, str]:
    for key in ["DEEPSEEK_API_KEY", "DEEPSEEK_KEY", "AI_API_KEY"]:
        val = os.getenv(key)
        if val:
            return val, key
    return "", ""


def call_deepseek(
    api_key: str,
    system_prompt: str,
    user_prompt: str,
    model: str = "deepseek-chat",
    temperature: float = 0.2,
    max_tokens: int = 800
) -> str:
    url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1").rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code != 200:
        logging.error("DeepSeek request failed: %s", resp.text)
        raise RuntimeError(resp.text[:300])
    data = resp.json()
    choices = data.get("choices", [])
    if not choices:
        raise RuntimeError("Empty response from DeepSeek.")
    return choices[0]["message"]["content"].strip()
