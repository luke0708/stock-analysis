from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from stock_analysis.bridge.original_param_lock import LOCKED_ORIGINAL_ENV


DEFAULT_ORIGINAL_PROJECT = Path(__file__).resolve().parents[2] / "vendor" / "daily_stock_analysis"
DEFAULT_WORKSPACE_ENV = Path(__file__).resolve().parents[2] / ".env"
ENV_PREFIXES = ("GEMINI_", "OPENAI_", "TAVILY_", "BOCHA_", "BRAVE_", "SERPAPI_")
ENV_EXACT_KEYS = ("TUSHARE_TOKEN", "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")
ENV_FORCE_DEFAULTS: Dict[str, str] = {
    # Keep numeric/bool config parseable even when workspace .env omits them.
    "GEMINI_MODEL": LOCKED_ORIGINAL_ENV["GEMINI_MODEL"],
    "GEMINI_MODEL_FALLBACK": LOCKED_ORIGINAL_ENV["GEMINI_MODEL_FALLBACK"],
    "GEMINI_TEMPERATURE": LOCKED_ORIGINAL_ENV["GEMINI_TEMPERATURE"],
    "GEMINI_REQUEST_DELAY": LOCKED_ORIGINAL_ENV["GEMINI_REQUEST_DELAY"],
    "GEMINI_MAX_RETRIES": LOCKED_ORIGINAL_ENV["GEMINI_MAX_RETRIES"],
    "GEMINI_RETRY_DELAY": LOCKED_ORIGINAL_ENV["GEMINI_RETRY_DELAY"],
    "OPENAI_MODEL": LOCKED_ORIGINAL_ENV["OPENAI_MODEL"],
    "OPENAI_TEMPERATURE": LOCKED_ORIGINAL_ENV["OPENAI_TEMPERATURE"],
    "SAVE_CONTEXT_SNAPSHOT": LOCKED_ORIGINAL_ENV["SAVE_CONTEXT_SNAPSHOT"],
    "ENABLE_REALTIME_QUOTE": LOCKED_ORIGINAL_ENV["ENABLE_REALTIME_QUOTE"],
    "ENABLE_CHIP_DISTRIBUTION": LOCKED_ORIGINAL_ENV["ENABLE_CHIP_DISTRIBUTION"],
    "REALTIME_SOURCE_PRIORITY": LOCKED_ORIGINAL_ENV["REALTIME_SOURCE_PRIORITY"],
    "REALTIME_CACHE_TTL": LOCKED_ORIGINAL_ENV["REALTIME_CACHE_TTL"],
    # Block fallback from original .env for missing secrets/search keys.
    "GEMINI_API_KEY": "",
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "TAVILY_API_KEY": "",
    "TAVILY_API_KEYS": "",
    "BOCHA_API_KEY": "",
    "BOCHA_API_KEYS": "",
    "BRAVE_API_KEY": "",
    "BRAVE_API_KEYS": "",
    "SERPAPI_KEY": "",
    "SERPAPI_KEYS": "",
    "TUSHARE_TOKEN": "",
    "HTTP_PROXY": "",
    "HTTPS_PROXY": "",
    "NO_PROXY": "",
}


@dataclass
class BridgeResult:
    success: bool
    query_id: str
    analysis_time: Optional[str]
    raw_result: Dict[str, Any]
    context_snapshot: Optional[Dict[str, Any]]
    duration_ms: int
    error: str = ""


def _tail_text(value: Any, limit: int = 600) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        text = value.decode("utf-8", errors="ignore")
    else:
        text = str(value)
    normalized = " ".join(text.split())
    if not normalized:
        return ""
    if len(normalized) <= limit:
        return normalized
    return f"...{normalized[-limit:]}"


def _pick_original_python(original_project_root: Path, python_bin: Optional[Path] = None) -> Path:
    if python_bin:
        return Path(python_bin)
    venv_python = original_project_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def _is_runtime_override_key(key: str) -> bool:
    return key.startswith(ENV_PREFIXES) or key in ENV_EXACT_KEYS


def _clear_runtime_override_env(env: Dict[str, str]) -> None:
    for key in list(env.keys()):
        if _is_runtime_override_key(key):
            env.pop(key, None)


def _parse_dotenv_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    parsed: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("export "):
            text = text[7:].strip()
        if "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip()
        # Support inline comments in unquoted dotenv values:
        # KEY=value  # comment
        if value and value[0] not in {"'", '"'}:
            value = re.sub(r"\s+#.*$", "", value).strip()
        if len(value) >= 2 and ((value[0] == value[-1] == '"') or (value[0] == value[-1] == "'")):
            value = value[1:-1]
        if _is_runtime_override_key(key):
            parsed[key] = value
    return parsed


def _runner_script() -> str:
    return textwrap.dedent(
        """
        import json
        import os
        import sys
        from pathlib import Path

        project_root = Path(sys.argv[1]).resolve()
        stock_code = sys.argv[2].strip()
        report_type = sys.argv[3].strip().lower()
        query_id = sys.argv[4].strip()
        output_path = Path(sys.argv[5]).resolve()

        payload = {
            "success": False,
            "query_id": query_id,
            "analysis_time": None,
            "raw_result": {},
            "context_snapshot": None,
            "error": "",
        }

        try:
            if not project_root.exists():
                raise RuntimeError(f"original project not found: {project_root}")

            os.chdir(str(project_root))
            sys.path.insert(0, str(project_root))

            from src.core.pipeline import StockAnalysisPipeline
            from src.enums import ReportType
            from src.storage import get_db

            report_enum = ReportType.SIMPLE if report_type == "simple" else ReportType.FULL

            pipeline = StockAnalysisPipeline(
                query_id=query_id,
                query_source="beta_ui",
                save_context_snapshot=True,
            )
            _ = pipeline.process_single_stock(
                code=stock_code,
                skip_analysis=False,
                single_stock_notify=False,
                report_type=report_enum,
            )

            db = get_db()
            records = db.get_analysis_history(query_id=query_id, limit=1)
            if not records:
                raise RuntimeError("no analysis_history record found by query_id")

            record = records[0]
            raw_text = record.raw_result or "{}"
            ctx_text = record.context_snapshot or ""

            try:
                raw_obj = json.loads(raw_text)
            except Exception:
                raw_obj = {}

            ctx_obj = None
            if ctx_text:
                try:
                    ctx_obj = json.loads(ctx_text)
                except Exception:
                    ctx_obj = None

            payload.update(
                {
                    "success": True,
                    "analysis_time": record.created_at.isoformat() if getattr(record, "created_at", None) else None,
                    "raw_result": raw_obj,
                    "context_snapshot": ctx_obj,
                    "error": "",
                }
            )

        except Exception as exc:
            payload["error"] = str(exc)

        output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        """
    )


def run_original_single_stock(
    stock_code: str,
    report_type: str = "simple",
    *,
    original_project_root: Path = DEFAULT_ORIGINAL_PROJECT,
    python_bin: Optional[Path] = None,
    timeout_seconds: int = 900,
    lock_original_params: bool = True,
    env_source: str = "workspace",
    workspace_env_path: Optional[Path] = None,
) -> BridgeResult:
    """Run original project's single-stock algorithm and return raw_result/context_snapshot.

    This function does not re-implement any algorithm logic; it only bridges execution.
    """
    if not stock_code or len(stock_code.strip()) != 6 or not stock_code.strip().isdigit():
        raise ValueError("stock_code must be a 6-digit code")

    report_type = (report_type or "simple").strip().lower()
    if report_type not in {"simple", "full"}:
        raise ValueError("report_type must be 'simple' or 'full'")

    query_id = f"beta_{stock_code}_{uuid.uuid4().hex[:12]}"
    py = _pick_original_python(Path(original_project_root), python_bin)

    with tempfile.NamedTemporaryFile(prefix="beta_bridge_", suffix=".json", delete=False) as tmp:
        out_path = Path(tmp.name)

    start = time.time()
    try:
        cmd = [
            str(py),
            "-c",
            _runner_script(),
            str(Path(original_project_root).resolve()),
            stock_code.strip(),
            report_type,
            query_id,
            str(out_path),
        ]
        child_env = os.environ.copy()
        if lock_original_params:
            child_env.update(LOCKED_ORIGINAL_ENV)

        env_mode = (env_source or "workspace").strip().lower()
        if env_mode == "workspace":
            _clear_runtime_override_env(child_env)
            env_path = Path(workspace_env_path) if workspace_env_path else DEFAULT_WORKSPACE_ENV
            workspace_overrides = _parse_dotenv_file(env_path)
            child_env.update(workspace_overrides)
            # Block original project's .env from filling missing keys in workspace mode.
            for key, default_value in ENV_FORCE_DEFAULTS.items():
                child_env.setdefault(key, default_value)
        elif env_mode == "original":
            _clear_runtime_override_env(child_env)
        elif env_mode == "inherit":
            pass
        else:
            raise ValueError("env_source must be 'workspace', 'original', or 'inherit'")

        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=child_env,
        )

        duration_ms = int((time.time() - start) * 1000)

        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "subprocess failed").strip()
            stderr_tail = _tail_text(proc.stderr)
            stdout_tail = _tail_text(proc.stdout)
            debug_tail_parts = []
            if stderr_tail:
                debug_tail_parts.append(f"stderr_tail={stderr_tail}")
            if stdout_tail:
                debug_tail_parts.append(f"stdout_tail={stdout_tail}")
            if debug_tail_parts:
                err = f"{err} | {'; '.join(debug_tail_parts)}"
            return BridgeResult(
                success=False,
                query_id=query_id,
                analysis_time=None,
                raw_result={},
                context_snapshot=None,
                duration_ms=duration_ms,
                error=err[:2000],
            )

        if not out_path.exists():
            return BridgeResult(
                success=False,
                query_id=query_id,
                analysis_time=None,
                raw_result={},
                context_snapshot=None,
                duration_ms=duration_ms,
                error="bridge output not found",
            )

        try:
            payload = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return BridgeResult(
                success=False,
                query_id=query_id,
                analysis_time=None,
                raw_result={},
                context_snapshot=None,
                duration_ms=duration_ms,
                error=f"invalid bridge payload: {exc}",
            )

        return BridgeResult(
            success=bool(payload.get("success")),
            query_id=payload.get("query_id") or query_id,
            analysis_time=payload.get("analysis_time"),
            raw_result=payload.get("raw_result") or {},
            context_snapshot=payload.get("context_snapshot"),
            duration_ms=duration_ms,
            error=(payload.get("error") or "")[:2000],
        )

    except subprocess.TimeoutExpired as exc:
        duration_ms = int((time.time() - start) * 1000)
        stderr_tail = _tail_text(getattr(exc, "stderr", None))
        stdout_tail = _tail_text(getattr(exc, "stdout", None))
        debug_tail_parts = []
        if stderr_tail:
            debug_tail_parts.append(f"stderr_tail={stderr_tail}")
        if stdout_tail:
            debug_tail_parts.append(f"stdout_tail={stdout_tail}")
        timeout_error = f"bridge timeout after {timeout_seconds}s"
        if debug_tail_parts:
            timeout_error = f"{timeout_error} | {'; '.join(debug_tail_parts)}"
        return BridgeResult(
            success=False,
            query_id=query_id,
            analysis_time=None,
            raw_result={},
            context_snapshot=None,
            duration_ms=duration_ms,
            error=timeout_error,
        )
    finally:
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass


__all__ = ["BridgeResult", "run_original_single_stock", "DEFAULT_ORIGINAL_PROJECT"]
