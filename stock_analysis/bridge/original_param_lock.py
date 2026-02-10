from __future__ import annotations

from typing import Dict


# Lock non-secret runtime parameters to the baseline of the original project.
# API keys / tokens are intentionally excluded and remain sourced from env/.env.
LOCKED_ORIGINAL_ENV: Dict[str, str] = {
    "GEMINI_MODEL": "gemini-3-flash-preview",
    "GEMINI_MODEL_FALLBACK": "gemini-2.5-flash",
    "GEMINI_TEMPERATURE": "0.7",
    "GEMINI_REQUEST_DELAY": "2.0",
    "GEMINI_MAX_RETRIES": "5",
    "GEMINI_RETRY_DELAY": "5.0",
    "OPENAI_MODEL": "gpt-4o-mini",
    "OPENAI_TEMPERATURE": "0.7",
    "SAVE_CONTEXT_SNAPSHOT": "true",
    "ENABLE_REALTIME_QUOTE": "true",
    "ENABLE_CHIP_DISTRIBUTION": "true",
    "REALTIME_SOURCE_PRIORITY": "tencent,akshare_sina,efinance,akshare_em",
    "REALTIME_CACHE_TTL": "600",
}


__all__ = ["LOCKED_ORIGINAL_ENV"]
