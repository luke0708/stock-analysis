# 原算法 vs Beta链路 一致性验收报告

- 生成时间: 2026-02-09T17:31:39
- 样本数: 1
- 通过: 1
- 失败: 0
- 通过率: 100.00%

| code | status | full_equal | mismatch_count | mismatch_fields | beta_error | original_error |
|---|---|---:|---:|---|---|---|
| 601899 | passed | Y | 0 | - | - | - |

## 判定口径
- `full_equal`: 原工程 raw_result 与 Beta链路 raw_result 的规范化 JSON 完全一致。
- `mismatch_fields`: 关键字段对账差异（评分/建议/趋势/置信度/策略点位/风险提示/结论摘要）。