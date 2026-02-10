# 开发落地说明（精简版）

## 主入口文档

- `股票分析算法/MVP任务化复刻实施清单.md`

> 后续开发请以该文档为唯一执行清单。

## 归档文档（历史）

- `股票分析算法/archive_v1/规则映射表_v1.md`
- `股票分析算法/archive_v1/字段接口草案_v1.md`
- `股票分析算法/archive_v1/实现任务拆分清单_v1.md`
- `股票分析算法/archive_v1/页面分组展示清单_v1.md`

## 当前代码文件

- `股票分析算法/trend_signal.py`
- `股票分析算法/ui_mapping.py`
- `股票分析算法/demo_run.py`
- `stock_analysis/tasks/consistency_audit.py`

## Demo 命令

```bash
python3 股票分析算法/demo_run.py
```

输出：

- `股票分析算法/demo_trend_signal_output.json`
- `股票分析算法/demo_display_panels_output.json`

## 一致性验收命令（原算法 vs Beta链路）

```bash
python3 -m stock_analysis.tasks.consistency_audit \
  --codes 601899,600519,000001 \
  --report-type simple \
  --timeout 900
```

或使用样本文件：

```bash
python3 -m stock_analysis.tasks.consistency_audit \
  --codes-file 股票分析算法/samples/consistency_codes_10.txt \
  --report-type simple \
  --timeout 900
```

输出：

- `股票分析算法/reports/consistency_audit_*.json`
- `股票分析算法/reports/consistency_audit_*.csv`
- `股票分析算法/reports/consistency_audit_*.md`

当前保留基线（已验证通过）：

- `股票分析算法/reports/consistency_audit_20260209_173102.json`
- `股票分析算法/reports/consistency_audit_20260209_173102.csv`
- `股票分析算法/reports/consistency_audit_20260209_173102.md`
- `股票分析算法/reports/env_alignment_check_after_deps_ok.json`

## 环境对齐命令（一次性排查）

```bash
python3 -m stock_analysis.tasks.env_alignment_check \
  --probe-network \
  --json-out 股票分析算法/reports/env_alignment_check.json
```

如果要同时做一单桥接冒烟（会调用原算法，可能较慢）：

```bash
python3 -m stock_analysis.tasks.env_alignment_check \
  --probe-network \
  --bridge-smoke \
  --smoke-code 601899 \
  --smoke-timeout 240 \
  --json-out 股票分析算法/reports/env_alignment_check_with_smoke.json
```

说明：

- 桥接超时现在会自动携带子进程日志尾部（`stdout/stderr tail`），用于定位卡在数据源还是 LLM。
- 如果 `consistency_audit` 显示 `bridge timeout after ...`，优先跑上面的 `--bridge-smoke`，再把 JSON 报告发我。
- 历史排查阶段的中间报告可按需清理，仅保留当前基线报告即可。

## 环境变量来源说明（桥接层）

- 默认：`workspace`（使用本工程 `.env`，路径 `读取股票当天数据/.env`）
- 可选：`original`（使用原工程 `.env`）
- 可选：`inherit`（继承当前 shell 环境变量）
- 说明：`workspace` 模式会阻止原工程 `.env` 自动回填，若本工程未配置 API Key 会直接按“未配置”处理。
- 运行算法默认路径：`vendor/daily_stock_analysis`（本工程内镜像，不依赖外部工程文件）。

快速对比示例（同一股票跑两次）：

```bash
python3 - <<'PY'
from stock_analysis.bridge import run_original_single_stock

for mode in ("workspace", "original"):
    r = run_original_single_stock("601899", report_type="simple", timeout_seconds=120, env_source=mode)
    print(mode, "success=", r.success, "query_id=", r.query_id, "error=", (r.error or "")[:120])
PY
```
