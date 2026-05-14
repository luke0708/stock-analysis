"""
AI client helpers for DeepSeek.
"""
from __future__ import annotations

import logging
import os
import time
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
    model: str = "deepseek-v4-flash",
    temperature: float = 0.2,
    max_tokens: int = 4000,
    timeout: int = 90,
    max_retries: int = 2
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
    retryable_status = {429, 500, 502, 503, 504}
    last_error: Exception | None = None

    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        except requests.exceptions.Timeout as exc:
            last_error = exc
            logging.warning("DeepSeek request timed out (attempt %s/%s)", attempt + 1, max_retries + 1)
            if attempt < max_retries:
                time.sleep(1.5 ** attempt)
                continue
            raise RuntimeError("DeepSeek request timed out.")
        except requests.exceptions.RequestException as exc:
            last_error = exc
            logging.warning("DeepSeek request error (attempt %s/%s): %s", attempt + 1, max_retries + 1, exc)
            if attempt < max_retries:
                time.sleep(1.5 ** attempt)
                continue
            raise RuntimeError("DeepSeek request failed.")

        if resp.status_code in retryable_status and attempt < max_retries:
            logging.warning("DeepSeek retryable status: %s", resp.status_code)
            time.sleep(1.5 ** attempt)
            continue

        if resp.status_code != 200:
            logging.error("DeepSeek request failed: %s", resp.text)
            raise RuntimeError(resp.text[:300])

        data = resp.json()
        choices = data.get("choices", [])
        if not choices:
            if attempt < max_retries:
                time.sleep(1.5 ** attempt)
                continue
            raise RuntimeError("Empty response from DeepSeek.")
            
        message = choices[0].get("message", {})
        content = message.get("content", "")
        
        if not content:
            if attempt < max_retries:
                time.sleep(1.5 ** attempt)
                continue
            raise RuntimeError("Empty response from DeepSeek.")
            
        return content.strip()

    if last_error:
        raise RuntimeError(str(last_error))
    raise RuntimeError("DeepSeek request failed.")
