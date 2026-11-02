# 内容任务规划 Agent（Content Planning Agent）

小影科技 2027 校招 AI Agent 笔试题第 2 题：帮助运营人员在**预算与截止时间**
内完成内容活动方案。基于 Python 标准库原生实现，默认离线运行，无需任何
第三方依赖。

## 1. 项目简介

Agent 通过 ReAct 循环完成任务规划：

```
模型选择动作 → 执行工具 → 观察结果 → 模型调整下一步或结束
```

当出现**成本超限、工具失败**时，Agent 会重规划切换替代方案，保留已成功
步骤的结果；无可行方案时返回未完成及缺口，不把失败步骤记为成功。

## 2. 环境要求

- Python 3.9+（本机开发环境 Python 3.13）
- 默认离线运行，无需安装依赖、无需 API Key。

## 3. 安装与运行

```bash
# 进入项目目录
cd content-planning-agent

# 查看全部任务
python run.py --list

# 场景一：正常完成（初始方案 12 超预算，自动重规划到替代方案 8 后保存）
python run.py --task T01 --tag normal

# 场景二：缺预算 / 缺截止时间
python run.py --task T02 --tag missing_budget
python run.py --task T03 --tag missing_deadline

# 场景三：工具一次性失败后失败续跑（加分项）
python run.py --task T01 --fail-tool-once script_generator --tag tool_fail_recover

# 场景四：无可行方案（预算 5，两方案均超）
python run.py --task T04 --tag no_feasible

# 场景五：重复执行（验证幂等）
python run.py --task T05 --repeat 2
```

## 4. 运行测试

```bash
python -m unittest discover -s tests
```

预期：9 个测试全部通过。

## 5. 目录结构

```
content-planning-agent/
├── README.md
├── requirements.txt        # 依赖说明（默认无第三方依赖）
├── .env.example            # 环境变量示例
├── .gitignore
├── run.py                  # CLI 入口
├── src/
│   ├── agent.py            # ReAct 重规划循环
│   ├── llm.py              # MockLLM / RealLLM
│   ├── data_store.py       # 数据加载与运行期状态
│   └── tools/              # 四个工具
├── data/                   # 任务、工具费用耗时、素材
├── tests/                  # 单元测试
├── examples/traces/        # 8 份场景 Trace
└── docs/                   # 01~05 五份文档
```

## 6. 评审入口

- 需求与验收点：`docs/01-requirements.md`
- 方案与重规划：`docs/02-solution.md`
- 测试结果：`docs/03-evaluation.md`
- 场景 Trace：`examples/traces/`

## 7. 真实模型接入（可选）

配置环境变量后自动启用 RealLLM（OpenAI 兼容接口，基于 `urllib`）：

```bash
# 复制环境变量模板并填写
cp .env.example .env
#  设置 LLM_API_KEY、LLM_BASE_URL、LLM_MODEL
```

未配置 `LLM_API_KEY` 时始终使用离线 MockLLM。Mock 仅验证流程，不代表真实
模型决策效果。
