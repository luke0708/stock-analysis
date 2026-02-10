# MVP任务化复刻实施清单

## 0. 目标与原则

- 目标：抛弃原工程 UI，只复刻原工程算法链路，使用当前项目 `🧩 AI决策面板 (Beta)` 展示结果。
- 原则：
  - 算法 100% 复刻，不做本地推算替代。
  - `Beta` 只展示原始结构化结果（`raw_result`）与原始上下文快照（`context_snapshot`）。
  - 单股异步任务优先，先不做批量。

## 1. 文档精简策略

### 1.1 保留文档

- `股票分析算法/MVP任务化复刻实施清单.md`（本文件，唯一主入口）
- `股票分析算法/README_开发落地.md`（简要索引）

### 1.2 归档文档（保留不删除）

- `股票分析算法/archive_v1/规则映射表_v1.md`
- `股票分析算法/archive_v1/字段接口草案_v1.md`
- `股票分析算法/archive_v1/实现任务拆分清单_v1.md`
- `股票分析算法/archive_v1/页面分组展示清单_v1.md`

---

## 2. 范围边界（必须锁定）

### 2.1 算法来源（只参考）

- 本工程镜像代码（运行默认路径）：
  - `vendor/daily_stock_analysis/src/core/pipeline.py`
  - `vendor/daily_stock_analysis/src/analyzer.py`
  - `vendor/daily_stock_analysis/src/storage.py`
  - `vendor/daily_stock_analysis/data_provider/*.py`
- 外部原工程路径仅用于“设计对照阅读”，不作为运行依赖。

### 2.2 明确不参考

- `vendor/daily_stock_analysis/dashboard/**`
- `vendor/daily_stock_analysis/apps/**`
- 当前项目内任何本地推算“策略点位”的逻辑（后续移除）

---

## 3. 文件级实施清单

## 3.1 新增（当前工程）

1. `stock_analysis/tasks/job_models.py`
- 定义任务状态枚举与数据类：`pending/running/succeeded/failed`。

2. `stock_analysis/tasks/job_store.py`
- SQLite 表初始化与 CRUD（任务表、结果表）。

3. `stock_analysis/tasks/job_runner.py`
- Worker 主循环，单次只跑一个任务（避免资源争抢）。

4. `stock_analysis/bridge/original_algo_runner.py`
- 算法桥接层：调用原工程分析入口（不改原算法）。
- 输入：股票代码、报告类型、请求来源。
- 输出：`raw_result`、`context_snapshot`、`query_id`、耗时、错误信息。

5. `stock_analysis/bridge/original_algo_parser.py`
- 从原工程结果结构抽取标准展示字段：
  - `raw_result`（完整结构化）
  - `context_snapshot`（enhanced_context + raw inputs）
  - `meta`（query_id/time/source）

6. `stock_analysis/ui/beta_task_page.py`
- Beta 任务页面（可并入现有 `future_features.py`）：
  - 提交任务
  - 查看任务状态
  - 展示最近成功结果

## 3.2 修改（当前工程）

1. `stock_analysis/ui/future_features.py`
- 删除/停用 `_build_beta_raw_result` 中“策略点位本地推算”路径。
- 展示层只读任务结果中的 `raw_result.dashboard.battle_plan.sniper_points`。
- 无原始点位时显示“暂无原始策略点位”。

2. `stock_analysis/ui/unified_app.py`
- 将 `🧩 AI决策面板 (Beta)` 指向任务化页面。

3. `stock_analysis/core/cache_manager.py`（可选）
- 增加任务状态缓存清理入口（减少 session 污染）。

---

## 4. 接口级实施清单

## 4.1 内部任务接口（先做本地函数，不强依赖 HTTP）

1. `submit_single_stock_job(req) -> {job_id}`
- 入参：
  - `stock_code: str`
  - `report_type: "simple"|"detailed"`（MVP 默认 `simple`）
  - `requested_by: "beta_ui"`
- 出参：`job_id`

2. `get_job_status(job_id) -> {status, progress, message}`
- `status`: `pending/running/succeeded/failed`

3. `get_job_result(job_id) -> {meta, raw_result, context_snapshot}`
- 仅 `succeeded` 可返回完整内容。

4. `run_one_job(job_id) -> None`
- Worker 调用；失败写入 `error_message`。

## 4.2 算法桥接接口

1. `run_original_single_stock(stock_code, report_type) -> BridgeResult`
- 必须复用原工程算法链路，不自行计算指标。
- `BridgeResult` 包含：
  - `query_id`
  - `analysis_time`
  - `raw_result`（完整）
  - `context_snapshot`（完整）
  - `duration_ms`
  - `success/error`

---

## 5. 表结构级实施清单（SQLite）

## 5.1 `analysis_jobs`

- `id` INTEGER PK
- `job_id` TEXT UNIQUE
- `stock_code` TEXT NOT NULL
- `report_type` TEXT NOT NULL DEFAULT 'simple'
- `status` TEXT NOT NULL  -- pending/running/succeeded/failed
- `requested_by` TEXT
- `created_at` DATETIME NOT NULL
- `started_at` DATETIME
- `finished_at` DATETIME
- `duration_ms` INTEGER
- `retry_count` INTEGER DEFAULT 0
- `error_message` TEXT

索引：
- `idx_jobs_status_created(status, created_at)`
- `idx_jobs_stock_created(stock_code, created_at)`

## 5.2 `analysis_results`

- `id` INTEGER PK
- `job_id` TEXT UNIQUE NOT NULL
- `query_id` TEXT
- `analysis_time` DATETIME
- `source` TEXT DEFAULT 'original_algo'
- `raw_result_json` TEXT NOT NULL
- `context_snapshot_json` TEXT
- `created_at` DATETIME NOT NULL

索引：
- `idx_results_query_id(query_id)`
- `idx_results_created(created_at)`

---

## 6. 执行流程（MVP）

1. 用户在 Beta 页提交代码。
2. 写入 `analysis_jobs(pending)`。
3. Worker 取任务 -> 标记 `running`。
4. 调用 `original_algo_runner`（耗时几分钟正常）。
5. 成功：落 `analysis_results`，任务改 `succeeded`。
6. 失败：任务改 `failed`，写错误。
7. Beta 页轮询状态并渲染最新成功结果。

---

## 7. 非目标（MVP 暂不做）

- 批量分析任务
- 两套数据源合并
- 算法参数优化/阈值微调
- 实时秒级刷新

---

## 8. 验收标准

1. 同一股票同一时间点，Beta 展示的 `策略点位/结论摘要/风险提示` 与原工程 `raw_result` 一致。
2. Beta 不出现本地推算策略点位。
3. 单股任务可稳定完成（允许 2-5 分钟）。
4. 失败可追踪（有错误信息和任务状态）。

### 8.1 一致性验收脚本入口

- 脚本：`stock_analysis/tasks/consistency_audit.py`
- 目标：批量股票（建议 10-20 只）执行“原工程记录 vs Beta链路结果”对账。
- 核心校验：
  - `full_equal`: `raw_result` 规范化 JSON 全量一致
  - `mismatch_fields`: 评分/建议/趋势/置信度/策略点位/风险提示/结论摘要等关键字段差异

### 8.2 参数锁定（避免版本漂移）

- 锁定文件：`stock_analysis/bridge/original_param_lock.py`
- 作用：桥接运行原算法时，固定关键非密钥参数（模型名、温度、实时口径等）。
- 原则：仅锁定“口径参数”，不写入 API Key/Token 等敏感信息。
- 环境变量来源：`run_original_single_stock(..., env_source="workspace")` 默认使用当前工程 `.env`。

---

## 9. 下一步实施顺序（建议）

1. 先落库：`analysis_jobs` + `analysis_results`。
2. 再桥接：`original_algo_runner` 单股跑通。
3. 再接 UI：Beta 提交任务 + 状态轮询 + 结果展示。
4. 最后清理 Beta 旧推算分支，锁定“只读原始结果”。
