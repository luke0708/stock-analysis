from __future__ import annotations

from typing import Any, Dict, Optional


def build_bridge_payload(
    *,
    query_id: str,
    analysis_time: Optional[str],
    raw_result: Dict[str, Any],
    context_snapshot: Optional[Dict[str, Any]],
    source: str = "original_algo",
) -> Dict[str, Any]:
    """Build a normalized payload consumed by Beta UI and job store."""
    return {
        "meta": {
            "query_id": query_id,
            "analysis_time": analysis_time,
            "source": source,
        },
        "raw_result": raw_result or {},
        "context_snapshot": context_snapshot,
    }


def extract_sniper_points(raw_result: Dict[str, Any]) -> Dict[str, Any]:
    dashboard = (raw_result or {}).get("dashboard") or {}
    battle = dashboard.get("battle_plan") or {}
    sniper = battle.get("sniper_points") or {}
    return {
        "ideal_buy": sniper.get("ideal_buy"),
        "secondary_buy": sniper.get("secondary_buy"),
        "stop_loss": sniper.get("stop_loss"),
        "take_profit": sniper.get("take_profit"),
    }
