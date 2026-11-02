# 03 测试与评估

## 1. 测试方式

- 单元测试：`tests/test_agent.py`，基于标准库 `unittest`。
- 场景验证：`run.py` 生成的 Trace 存于 `examples/traces/`。

运行命令：

```bash
python -m unittest discover -s tests
```

## 2. 测试预期与实际结果

| 测试方法 | 预期 | 实际 |
| --- | --- | --- |
| test_normal_completion_with_replan | 重规划后 standard 完成，成本 8 | 通过 |
| test_missing_budget_blocked | 缺预算阻断，不执行步骤 | 通过 |
| test_missing_deadline_blocked | 缺截止时间阻断 | 通过 |
| test_no_feasible_plan_blocked | 无可行方案、返回缺口、不保存 | 通过 |
| test_fail_once_then_recover | 一次性失败后续跑成功 | 通过 |
| test_persistent_tool_failure_blocked | 持续失败阻断，不记为成功 | 通过 |
| test_repeated_execution_is_idempotent | 第二次重复，仅一份方案 | 通过 |
| test_nonexistent_task_blocked | 任务不存在阻断 | 通过 |
| test_step_limit_returns_incomplete | 步数上限返回 incomplete | 通过 |

实际运行结果：**9 个测试全部通过**。

## 3. 场景 Trace 核对

| 场景 | 最终状态 | 关键核对项 |
| --- | --- | --- |
| T01 normal | completed | 成本 12→8，replan_count=1，已保存 |
| T01 tool_fail_recover | completed | 脚本首次失败，复用素材，8 步成功 |
| T01 tool_fail | blocked | 脚本持续失败，未记为成功 |
| T02 missing_budget | blocked | 提示缺 budget，未执行 |
| T03 missing_deadline | blocked | 提示缺 deadline |
| T04 no_feasible | blocked | 最小成本 8，预算缺口 3，未保存 |
| T05 repeat_1 / repeat_2 | completed | 第二次 duplicated=true，仅一份方案 |

## 4. 已知限制

1. MockLLM 为规则式决策，只验证流程与重规划，不证明真实模型决策能力。
2. 截止时间仅做完整性校验，未与耗时做钟点换算（避免口径不一致）。
3. 数据均为内存态，进程结束后运行期方案不持久化（Trace 文件除外）。
4. 未实现界面、线上部署与多 Agent，题目说明这些均非必需。
