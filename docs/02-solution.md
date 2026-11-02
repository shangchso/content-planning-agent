# 02 方案设计

## 1. 总体架构

```
content-planning-agent/
├── run.py                # CLI 入口
├── src/
│   ├── agent.py          # ReAct 重规划循环
│   ├── llm.py            # MockLLM / RealLLM 决策模型
│   ├── data_store.py     # 数据加载与运行期状态
│   └── tools/            # 四个业务工具
├── data/                 # 合成数据
├── tests/                # 单元测试
├── examples/traces/      # 场景 Trace
└── docs/                 # 文档
```

## 2. ReAct 调用流程

核心循环位于 `src/agent.py`：

```
模型选择动作 → 执行工具 → 观察结果 → 更新状态 → 模型决定下一步或结束
```

- 每轮决策由 `llm.decide(state)` 输出动作与决策依据。
- Agent 调用对应工具并根据观察结果更新 `state`。
- 达到 `max_steps` 时强制结束并返回 `incomplete`。

## 3. 两套方案与重规划

`data/tools.json` 定义了按顺序尝试的两套方案：

| 方案 | 步骤费用（素材检索 + 脚本生成） | 总成本 | 总耗时 |
| --- | --- | --- | --- |
| premium 高端方案 | 4 + 8 | **12** | 5 |
| standard 标准替代方案 | 3 + 5 | **8** | 4 |

以 T01（预算 10）为例：

1. 执行 premium 方案，成本估算为 12，**超预算**（缺口 -2）。
2. 决策 `switch_plan` 切换到 standard。
3. 素材检索与方案无关，结果**保留复用**；脚本生成绑定方案，重新生成。
4. standard 估算为 8，在预算内（余量 2），保存并结束。

## 4. 工具失败处理

- **一次性失败**（`failed_tool_once`）：首次调用失败后自动恢复。Agent 切换
  方案并复用已成功步骤，最终完成，对应加分项「失败续跑」。
- **持续失败**（`failed_tool`）：该工具始终失败，替代方案也无法成功时，
  如实返回 `blocked`，不把失败记为成功。

## 5. 步骤状态与复用规则

| 步骤 | 跨方案复用 | 说明 |
| --- | --- | --- |
| material_search | 是 | 与方案无关，成功后保留 |
| script_generator | 否 | 绑定方案，切换后重新生成 |

## 6. 技术取舍

- **Python 原生实现**：仅使用标准库，不引入 Agent 框架，便于评审理解
  ReAct 与重规划的完整逻辑。
- **默认 MockLLM**：离线可运行，确定性复现全部场景；Mock 只验证流程，
  不代表真实模型决策效果。
- **预留 RealLLM**：通过 OpenAI 兼容接口与 `LLM_API_KEY` 启用，使用
  `urllib` 实现，未配置时自动回退 Mock。
