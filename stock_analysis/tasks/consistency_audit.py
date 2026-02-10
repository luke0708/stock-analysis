from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from stock_analysis.bridge.original_algo_runner import DEFAULT_ORIGINAL_PROJECT
from stock_analysis.tasks import (
    JobStore,
    get_job_result,
    run_one_pending_job,
    submit_single_stock_job,
)


def _now_tag() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _normalize_codes(codes: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in codes:
        code = (item or "").strip()
        if len(code) == 6 and code.isdigit() and code not in seen:
            seen.add(code)
            out.append(code)
    return out


def _load_codes(args: argparse.Namespace) -> List[str]:
    raw_codes: List[str] = []
    if args.codes:
        raw_codes.extend([x.strip() for x in args.codes.split(",")])
    if args.codes_file:
        file_path = Path(args.codes_file)
        if file_path.exists():
            text = file_path.read_text(encoding="utf-8")
            for token in text.replace("\n", ",").split(","):
                raw_codes.append(token.strip())
    return _normalize_codes(raw_codes)


def _pick_original_python(original_project_root: Path) -> Path:
    venv_python = original_project_root / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def _query_original_raw_result_by_query_id(
    *,
    query_id: str,
    original_project_root: Path,
    timeout_seconds: int,
) -> Dict[str, Any]:
    """Read original project's analysis_history.raw_result by query_id."""
    py = _pick_original_python(original_project_root)

    script = textwrap.dedent(
        """
        import json
        import os
        import sys
        from pathlib import Path

        project_root = Path(sys.argv[1]).resolve()
        query_id = sys.argv[2].strip()
        output_path = Path(sys.argv[3]).resolve()
        payload = {"success": False, "raw_result": {}, "error": ""}

        try:
            if not project_root.exists():
                raise RuntimeError(f"original project not found: {project_root}")
            os.chdir(str(project_root))
            sys.path.insert(0, str(project_root))

            from src.storage import get_db

            db = get_db()
            records = db.get_analysis_history(query_id=query_id, limit=1)
            if not records:
                raise RuntimeError("no analysis_history record found by query_id")

            record = records[0]
            raw_text = record.raw_result or "{}"
            try:
                raw_obj = json.loads(raw_text)
            except Exception:
                raw_obj = {}

            payload.update({"success": True, "raw_result": raw_obj, "error": ""})
        except Exception as exc:
            payload["error"] = str(exc)

        output_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        """
    )

    with tempfile.NamedTemporaryFile(prefix="audit_query_", suffix=".json", delete=False) as tmp:
        out_path = Path(tmp.name)

    try:
        cmd = [
            str(py),
            "-c",
            script,
            str(original_project_root.resolve()),
            query_id,
            str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or "query subprocess failed").strip()
            return {"success": False, "raw_result": {}, "error": err[:2000]}

        payload = json.loads(out_path.read_text(encoding="utf-8"))
        return {
            "success": bool(payload.get("success")),
            "raw_result": payload.get("raw_result") or {},
            "error": (payload.get("error") or "")[:2000],
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "raw_result": {}, "error": f"query timeout after {timeout_seconds}s"}
    except Exception as exc:
        return {"success": False, "raw_result": {}, "error": str(exc)}
    finally:
        out_path.unlink(missing_ok=True)


def _deep_get(data: Dict[str, Any], path: Sequence[str]) -> Any:
    cur: Any = data
    for key in path:
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _compare_raw_fields(original_raw: Dict[str, Any], beta_raw: Dict[str, Any]) -> Tuple[bool, List[Dict[str, Any]]]:
    fields: List[Tuple[str, Sequence[str]]] = [
        ("sentiment_score", ("sentiment_score",)),
        ("operation_advice", ("operation_advice",)),
        ("trend_prediction", ("trend_prediction",)),
        ("confidence_level", ("confidence_level",)),
        ("risk_alerts", ("dashboard", "intelligence", "risk_alerts")),
        ("sniper_points.ideal_buy", ("dashboard", "battle_plan", "sniper_points", "ideal_buy")),
        ("sniper_points.secondary_buy", ("dashboard", "battle_plan", "sniper_points", "secondary_buy")),
        ("sniper_points.stop_loss", ("dashboard", "battle_plan", "sniper_points", "stop_loss")),
        ("sniper_points.take_profit", ("dashboard", "battle_plan", "sniper_points", "take_profit")),
        ("analysis_summary", ("analysis_summary",)),
    ]
    mismatches: List[Dict[str, Any]] = []
    for label, path in fields:
        left = _deep_get(original_raw, path)
        right = _deep_get(beta_raw, path)
        if left != right:
            mismatches.append({"field": label, "original": left, "beta": right})

    full_equal = _canonical_json(original_raw) == _canonical_json(beta_raw)
    return full_equal, mismatches


def _run_single_stock_audit(
    *,
    code: str,
    report_type: str,
    store: JobStore,
    timeout_seconds: int,
    original_project_root: Path,
) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "stock_code": code,
        "report_type": report_type,
        "job_id": "",
        "query_id": "",
        "job_status": "",
        "audit_status": "failed",
        "full_equal": False,
        "mismatch_count": 0,
        "mismatch_fields": "",
        "beta_error": "",
        "original_error": "",
        "duration_ms": "",
        "sentiment_score": "",
        "operation_advice": "",
        "trend_prediction": "",
        "confidence_level": "",
    }

    job_id = submit_single_stock_job(code, report_type=report_type, requested_by="consistency_audit", store=store)[
        "job_id"
    ]
    row["job_id"] = job_id

    outcome: Dict[str, Any] = {}
    for _ in range(300):
        outcome = run_one_pending_job(store=store, timeout_seconds=timeout_seconds)
        # Ignore unrelated pending tasks in a reused db; only accept our submitted job.
        if outcome.get("job_id") == job_id:
            break
        if outcome.get("status") == "idle":
            break

    row["job_status"] = outcome.get("status", "")
    row["duration_ms"] = outcome.get("duration_ms", "")
    if outcome.get("status") != "succeeded":
        if outcome.get("job_id") != job_id and outcome.get("status") != "idle":
            row["beta_error"] = "submitted job was not picked from queue"
        else:
            row["beta_error"] = (outcome.get("error") or outcome.get("message") or "job failed")[:500]
        return row

    payload = get_job_result(job_id, store=store)
    if payload.get("error"):
        row["beta_error"] = str(payload.get("error"))[:500]
        return row

    meta = payload.get("meta") or {}
    beta_raw = payload.get("raw_result") or {}
    query_id = meta.get("query_id") or ""
    row["query_id"] = query_id
    row["sentiment_score"] = beta_raw.get("sentiment_score", "")
    row["operation_advice"] = beta_raw.get("operation_advice", "")
    row["trend_prediction"] = beta_raw.get("trend_prediction", "")
    row["confidence_level"] = beta_raw.get("confidence_level", "")
    if not query_id:
        row["beta_error"] = "missing query_id from beta result meta"
        return row

    origin_payload = _query_original_raw_result_by_query_id(
        query_id=query_id,
        original_project_root=original_project_root,
        timeout_seconds=min(timeout_seconds, 180),
    )
    if not origin_payload.get("success"):
        row["original_error"] = str(origin_payload.get("error") or "query original failed")[:500]
        return row

    original_raw = origin_payload.get("raw_result") or {}
    full_equal, mismatches = _compare_raw_fields(original_raw, beta_raw)

    row["full_equal"] = full_equal
    row["mismatch_count"] = len(mismatches)
    row["mismatch_fields"] = ",".join(m["field"] for m in mismatches)
    row["audit_status"] = "passed" if full_equal and not mismatches else "failed"

    if not full_equal and not mismatches:
        # Extremely unlikely branch: canonical JSON mismatch but no tracked-field mismatch.
        row["mismatch_fields"] = "untracked_fields"

    return row


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    headers = [
        "stock_code",
        "report_type",
        "job_id",
        "query_id",
        "job_status",
        "audit_status",
        "full_equal",
        "mismatch_count",
        "mismatch_fields",
        "beta_error",
        "original_error",
        "duration_ms",
        "sentiment_score",
        "operation_advice",
        "trend_prediction",
        "confidence_level",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in headers})


def _build_markdown_report(summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("# 原算法 vs Beta链路 一致性验收报告")
    lines.append("")
    lines.append(f"- 生成时间: {summary['generated_at']}")
    lines.append(f"- 样本数: {summary['total']}")
    lines.append(f"- 通过: {summary['passed']}")
    lines.append(f"- 失败: {summary['failed']}")
    lines.append(f"- 通过率: {summary['pass_rate']:.2f}%")
    lines.append("")
    lines.append("| code | status | full_equal | mismatch_count | mismatch_fields | beta_error | original_error |")
    lines.append("|---|---|---:|---:|---|---|---|")
    for row in rows:
        lines.append(
            "| {code} | {status} | {full} | {count} | {fields} | {be} | {oe} |".format(
                code=row.get("stock_code", ""),
                status=row.get("audit_status", ""),
                full="Y" if row.get("full_equal") else "N",
                count=row.get("mismatch_count", 0),
                fields=(row.get("mismatch_fields", "") or "-"),
                be=(row.get("beta_error", "") or "-"),
                oe=(row.get("original_error", "") or "-"),
            )
        )
    lines.append("")
    lines.append("## 判定口径")
    lines.append("- `full_equal`: 原工程 raw_result 与 Beta链路 raw_result 的规范化 JSON 完全一致。")
    lines.append("- `mismatch_fields`: 关键字段对账差异（评分/建议/趋势/置信度/策略点位/风险提示/结论摘要）。")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit consistency between original algorithm and Beta task chain.")
    parser.add_argument("--codes", type=str, default="", help="comma-separated stock codes, e.g. 601899,600519")
    parser.add_argument("--codes-file", type=str, default="", help="path to txt/csv file containing stock codes")
    parser.add_argument("--report-type", type=str, default="simple", choices=["simple", "detailed"])
    parser.add_argument("--timeout", type=int, default=900, help="timeout seconds per stock task")
    parser.add_argument(
        "--output-dir",
        type=str,
        default="股票分析算法/reports",
        help="directory to write json/csv/md reports",
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="",
        help="sqlite db path used by audit tasks",
    )
    parser.add_argument(
        "--original-project-root",
        type=str,
        default=str(DEFAULT_ORIGINAL_PROJECT),
        help="path to original project root",
    )
    args = parser.parse_args()

    codes = _load_codes(args)
    if not codes:
        print("[error] no valid stock codes provided. Use --codes or --codes-file.")
        return 2

    tag = _now_tag()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    db_path = Path(args.db_path) if args.db_path else Path(f"data/consistency_audit_{tag}.db")
    store = JobStore(db_path=db_path)
    original_project_root = Path(args.original_project_root)

    print(f"[info] start consistency audit, samples={len(codes)}, report_type={args.report_type}, timeout={args.timeout}s")
    rows: List[Dict[str, Any]] = []
    for idx, code in enumerate(codes, start=1):
        print(f"[run] {idx}/{len(codes)} code={code}")
        row = _run_single_stock_audit(
            code=code,
            report_type=args.report_type,
            store=store,
            timeout_seconds=args.timeout,
            original_project_root=original_project_root,
        )
        rows.append(row)
        print(
            "[done] code={code} status={status} full_equal={full} mismatches={m}".format(
                code=code,
                status=row.get("audit_status"),
                full=row.get("full_equal"),
                m=row.get("mismatch_count"),
            )
        )

    passed = len([r for r in rows if r.get("audit_status") == "passed"])
    total = len(rows)
    failed = total - passed
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": (passed / total * 100.0) if total else 0.0,
        "report_type": args.report_type,
        "timeout": args.timeout,
        "codes": codes,
        "db_path": str(db_path.resolve()),
    }

    json_path = output_dir / f"consistency_audit_{tag}.json"
    csv_path = output_dir / f"consistency_audit_{tag}.csv"
    md_path = output_dir / f"consistency_audit_{tag}.md"

    _write_json(json_path, {"summary": summary, "rows": rows})
    _write_csv(csv_path, rows)
    md_content = _build_markdown_report(summary, rows)
    md_path.write_text(md_content, encoding="utf-8")

    print(f"[ok] json => {json_path}")
    print(f"[ok] csv  => {csv_path}")
    print(f"[ok] md   => {md_path}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
