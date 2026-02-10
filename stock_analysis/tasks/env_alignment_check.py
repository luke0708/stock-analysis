from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from stock_analysis.bridge.original_algo_runner import run_original_single_stock


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_ENV_PATH = ROOT_DIR / ".env"
DEFAULT_VENDOR_ROOT = ROOT_DIR / "vendor" / "daily_stock_analysis"
DEFAULT_VENDOR_DB = DEFAULT_VENDOR_ROOT / "data" / "stock_analysis.db"


def _parse_dotenv(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    parsed: Dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and value[0] not in {"'", '"'}:
            value = re.sub(r"\s+#.*$", "", value).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        parsed[key] = value
    return parsed


def _env_status(key: str, env_file_vars: Dict[str, str]) -> Dict[str, Any]:
    value = os.getenv(key)
    source = "shell"
    if value is None:
        value = env_file_vars.get(key)
        source = ".env"
    if not value:
        return {"key": key, "status": "UNSET", "source": source}
    return {"key": key, "status": f"SET(len={len(value)})", "source": source}


def _probe_module(module_name: str) -> Dict[str, Any]:
    spec = importlib.util.find_spec(module_name)
    return {"module": module_name, "ok": bool(spec)}


def _probe_domain(domain: str, port: int, timeout_sec: float = 2.0) -> Dict[str, Any]:
    result: Dict[str, Any] = {"domain": domain, "port": port, "dns_ok": False, "tcp_ok": False, "error": ""}
    try:
        socket.gethostbyname(domain)
        result["dns_ok"] = True
    except Exception as exc:
        result["error"] = f"dns_error: {exc}"
        return result

    try:
        with socket.create_connection((domain, port), timeout=timeout_sec):
            result["tcp_ok"] = True
    except Exception as exc:
        result["error"] = f"tcp_error: {exc}"
    return result


def _check_vendor_db(db_path: Path) -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "db_path": str(db_path),
        "exists": db_path.exists(),
        "tables": [],
        "stock_daily_latest": [],
        "error": "",
    }
    if not db_path.exists():
        return info

    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        info["tables"] = [row[0] for row in cur.fetchall()]
        cur.execute(
            "SELECT code, MAX(date) AS max_date, COUNT(*) AS rows_cnt "
            "FROM stock_daily GROUP BY code ORDER BY max_date DESC LIMIT 5"
        )
        info["stock_daily_latest"] = [
            {"code": row[0], "max_date": row[1], "rows": row[2]} for row in cur.fetchall()
        ]
        conn.close()
    except Exception as exc:
        info["error"] = str(exc)
    return info


def run_env_alignment_check(
    *,
    env_path: Path,
    vendor_root: Path,
    probe_network: bool,
    run_bridge_smoke: bool,
    smoke_code: str,
    smoke_timeout: int,
    env_source: str,
) -> Dict[str, Any]:
    env_file_vars = _parse_dotenv(env_path)

    required_env = ["GEMINI_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL"]
    optional_env = [
        "TAVILY_API_KEYS",
        "BOCHA_API_KEYS",
        "BRAVE_API_KEYS",
        "SERPAPI_API_KEYS",
        "TUSHARE_TOKEN",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NO_PROXY",
    ]
    env_checks = [_env_status(k, env_file_vars) for k in required_env + optional_env]

    modules = [
        "dotenv",
        "sqlalchemy",
        "requests",
        "pandas",
        "efinance",
        "akshare",
        "google.generativeai",
        "openai",
        "yfinance",
        "tavily",
        "baostock",
        "pytdx",
    ]
    import_checks = [_probe_module(m) for m in modules]

    venv_python = ROOT_DIR / ".venv" / "bin" / "python"
    venv_version = ""
    if venv_python.exists():
        try:
            proc = subprocess.run(
                [str(venv_python), "-V"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            venv_version = (proc.stdout or proc.stderr or "").strip()
        except Exception as exc:
            venv_version = f"error: {exc}"

    report: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root_dir": str(ROOT_DIR),
        "env_path": str(env_path),
        "vendor_root": str(vendor_root),
        "python": {
            "current_executable": sys.executable,
            "current_version": sys.version.split()[0],
            "venv_python": str(venv_python),
            "venv_version": venv_version,
        },
        "env_checks": env_checks,
        "import_checks": import_checks,
        "vendor_db": _check_vendor_db(vendor_root / "data" / "stock_analysis.db"),
        "network_checks": [],
        "bridge_smoke": None,
    }

    if probe_network:
        domains = [
            ("push2his.eastmoney.com", 443),
            ("qt.gtimg.cn", 80),
            ("hq.sinajs.cn", 80),
            ("generativelanguage.googleapis.com", 443),
            ("api.openai.com", 443),
        ]
        report["network_checks"] = [_probe_domain(d, p) for d, p in domains]

    if run_bridge_smoke:
        try:
            result = run_original_single_stock(
                smoke_code,
                report_type="simple",
                timeout_seconds=smoke_timeout,
                original_project_root=vendor_root,
                env_source=env_source,
                workspace_env_path=env_path,
            )
            report["bridge_smoke"] = {
                "success": result.success,
                "query_id": result.query_id,
                "duration_ms": result.duration_ms,
                "error": (result.error or "")[:2000],
            }
        except Exception as exc:
            report["bridge_smoke"] = {"success": False, "error": str(exc)}

    return report


def _print_report(report: Dict[str, Any]) -> None:
    print(f"[info] generated_at={report['generated_at']}")
    py = report["python"]
    print(f"[python] current={py['current_version']} ({py['current_executable']})")
    print(f"[python] venv={py['venv_version']} ({py['venv_python']})")

    print("[env]")
    for item in report["env_checks"]:
        print(f"  - {item['key']}: {item['status']} ({item['source']})")

    missing_modules = [m["module"] for m in report["import_checks"] if not m["ok"]]
    print(f"[imports] missing={len(missing_modules)} -> {', '.join(missing_modules) if missing_modules else '-'}")

    db = report["vendor_db"]
    print(f"[vendor_db] exists={db['exists']} path={db['db_path']}")
    if db["tables"]:
        print(f"[vendor_db] tables={','.join(db['tables'])}")
    if db["stock_daily_latest"]:
        latest = db["stock_daily_latest"][0]
        print(
            f"[vendor_db] latest_daily code={latest['code']} date={latest['max_date']} rows={latest['rows']}"
        )
    if db["error"]:
        print(f"[vendor_db] error={db['error']}")

    if report["network_checks"]:
        print("[network]")
        for n in report["network_checks"]:
            print(
                f"  - {n['domain']}:{n['port']} dns_ok={n['dns_ok']} tcp_ok={n['tcp_ok']}"
                + (f" error={n['error']}" if n["error"] else "")
            )

    if report["bridge_smoke"] is not None:
        smoke = report["bridge_smoke"]
        print(
            f"[bridge_smoke] success={smoke.get('success')} duration_ms={smoke.get('duration_ms', '')} "
            f"query_id={smoke.get('query_id', '')}"
        )
        if smoke.get("error"):
            print(f"[bridge_smoke] error={smoke['error']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="环境对齐检查（解释器/依赖/env/网络/桥接）")
    parser.add_argument("--env-path", default=str(DEFAULT_ENV_PATH), help="workspace .env 路径")
    parser.add_argument("--vendor-root", default=str(DEFAULT_VENDOR_ROOT), help="vendor 原算法工程路径")
    parser.add_argument("--probe-network", action="store_true", help="检测关键域名 DNS/TCP 连通性")
    parser.add_argument("--bridge-smoke", action="store_true", help="执行一次桥接冒烟测试（可能较慢）")
    parser.add_argument("--smoke-code", default="601899", help="冒烟测试股票代码")
    parser.add_argument("--smoke-timeout", type=int, default=180, help="冒烟测试超时秒数")
    parser.add_argument(
        "--env-source",
        default="workspace",
        choices=["workspace", "original", "inherit"],
        help="桥接运行时环境来源",
    )
    parser.add_argument("--json-out", default="", help="可选：写出 JSON 报告文件")
    args = parser.parse_args()

    report = run_env_alignment_check(
        env_path=Path(args.env_path).resolve(),
        vendor_root=Path(args.vendor_root).resolve(),
        probe_network=args.probe_network,
        run_bridge_smoke=args.bridge_smoke,
        smoke_code=args.smoke_code.strip(),
        smoke_timeout=args.smoke_timeout,
        env_source=args.env_source,
    )
    _print_report(report)

    if args.json_out:
        out = Path(args.json_out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[ok] json => {out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
