# 示例与 Trace 说明

本目录存放各场景的输入、实际输出与运行 Trace。每个 Trace 文件包含完整的
ReAct 循环记录：每一步的动作、工具入参、观察摘要、决策依据，以及最终结果。

## Trace 文件与验收点对应关系

| Trace 文件 | 覆盖验收点 | 最终状态 |
| --- | --- | --- |
| `traces/trace_T01_normal.json` | 正常完成、预算超限重规划 | completed |
| `traces/trace_T01_tool_fail_recover.json` | 工具失败、失败续跑（加分项） | completed |
| `traces/trace_T01_tool_fail.json` | 工具持续失败、无替代方案 | blocked |
| `traces/trace_T02_missing_budget.json` | 缺预算 | blocked |
| `traces/trace_T03_missing_deadline.json` | 缺截止时间 | blocked |
| `traces/trace_T04_no_feasible.json` | 预算超限、无可行方案、返回缺口 | blocked |
| `traces/trace_T05_repeat_1.json` | 重复执行（首次保存） | completed |
| `traces/trace_T05_repeat_2.json` | 重复执行（幂等，不新建） | completed |

## 重新生成 Trace

在项目根目录执行：

```bash
python run.py --task T01 --tag normal
python run.py --task T01 --fail-tool-once script_generator --tag tool_fail_recover
python run.py --task T05 --repeat 2
```

每条 Trace 中的 `trace` 字段按时间顺序记录了「模型选择动作 → 执行工具 →
观察结果 → 模型调整下一步或结束」的完整过程，可直接用于评审。
