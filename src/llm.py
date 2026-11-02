"""决策模型层。

提供两种决策实现：
1. MockLLM：离线规则式决策模型，不依赖外部 API，根据当前状态与工具观察结果
   决定下一步动作，是本项目默认运行方式。
2. RealLLM：基于 OpenAI 兼容 Chat Completions 接口的真实大模型实现，
   通过环境变量配置；未配置密钥时自动回退到 MockLLM。

决策动作集合：
- material_search   素材检索
- script_generator  脚本生成
- estimate_cost     成本估算
- switch_plan       重规划（切换替代方案）
- save_plan         方案保存
- finish            正常结束
- block             阻断并结束
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any, Dict


class MockLLM:
    """离线 Mock 决策模型。"""

    def decide(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """根据当前状态返回下一步动作。"""
        # 1. 任务不存在
        if state["task_missing"]:
            return {
                "action": "block",
                "params": {"reason": "任务不存在，无法规划"},
                "rationale": "未找到任务数据，流程阻断",
                "terminal": True,
            }

        # 2. 输入完整性校验：缺预算或截止时间
        if state["missing_inputs"]:
            return {
                "action": "block",
                "params": {
                    "reason": f"缺少必要输入：{state['missing_inputs']}",
                },
                "rationale": "预算或截止时间缺失，不具备方案规划条件",
                "terminal": True,
            }

        current_plan = state["current_plan"]
        plan_steps = state["plan_steps"]
        step_index = state["current_step_index"]

        # 3. 上一步工具失败：需要重规划或阻断
        if state["need_replan"]:
            if state["has_alternative_plan"]:
                next_plan = state["plan_order"][state["plan_index"] + 1]
                return {
                    "action": "switch_plan",
                    "params": {
                        "from": current_plan,
                        "to": next_plan,
                        "reason": state["replan_reason"],
                    },
                    "rationale": (
                        f"工具执行失败（{state['replan_reason']}），"
                        f"重规划切换到替代方案 {next_plan}，保留已成功步骤结果"
                    ),
                    "terminal": False,
                }
            return {
                "action": "block",
                "params": {"reason": f"工具失败且无替代方案：{state['replan_reason']}"},
                "rationale": "失败后没有可行方案，返回未完成及缺口",
                "terminal": True,
            }

        # 4. 按顺序执行当前方案的步骤
        if step_index < len(plan_steps):
            tool = plan_steps[step_index]

            # 已成功的步骤直接复用（保留成功结果，不重复执行）
            if tool in state["completed_steps"]:
                completed = state["completed_steps"][tool]
                if completed.get("plan") == current_plan or tool == "material_search":
                    return {
                        "action": "reuse_step",
                        "params": {"tool": tool},
                        "rationale": (
                            f"步骤 {tool} 已成功完成，保留其结果并直接进入下一步"
                        ),
                        "terminal": False,
                    }

            rationale_map = {
                "material_search": "方案执行第一步，检索活动素材",
                "script_generator": "素材已就绪，生成活动脚本",
            }
            return {
                "action": tool,
                "params": {"plan": current_plan},
                "rationale": rationale_map.get(tool, "执行方案步骤"),
                "terminal": False,
            }

        # 4. 当前方案步骤全部完成，进行成本估算
        if state["cost_result"] is None:
            return {
                "action": "estimate_cost",
                "params": {"plan": current_plan},
                "rationale": "步骤已完成，估算方案总成本并与预算对比",
                "terminal": False,
            }

        cost = state["cost_result"]

        # 5. 超预算或步骤失败：尝试重规划到替代方案
        if not cost["within_budget"]:
            if state["has_alternative_plan"]:
                next_plan = state["plan_order"][state["plan_index"] + 1]
                return {
                    "action": "switch_plan",
                    "params": {"from": current_plan, "to": next_plan},
                    "rationale": (
                        f"当前方案总成本 {cost['total_cost']} 超过预算 {cost['budget']}，"
                        f"重规划切换到替代方案 {next_plan}，并保留已成功步骤结果"
                    ),
                    "terminal": False,
                }
            return {
                "action": "block",
                "params": {
                    "reason": (
                        f"所有方案均超预算，最小成本 {cost['total_cost']}，"
                        f"预算缺口 {cost['total_cost'] - cost['budget']}"
                    )
                },
                "rationale": "没有可行方案，返回未完成及缺口",
                "terminal": True,
            }

        # 6. 在预算内，保存方案
        if not state["save_done"]:
            return {
                "action": "save_plan",
                "params": {"plan": current_plan},
                "rationale": (
                    f"方案成本 {cost['total_cost']} 在预算 {cost['budget']} 内，保存方案"
                ),
                "terminal": False,
            }

        # 7. 保存结果处理
        if state["save_done"]:
            if state["save_ok"]:
                return {
                    "action": "finish",
                    "params": {},
                    "rationale": "方案已保存，任务完成",
                    "terminal": True,
                }
            return {
                "action": "block",
                "params": {"reason": "方案保存失败"},
                "rationale": "保存失败，如实返回，不把失败记为成功",
                "terminal": True,
            }

        return {
            "action": "block",
            "params": {"reason": "决策状态异常"},
            "rationale": "未匹配到已知决策分支，安全阻断",
            "terminal": True,
        }


class RealLLM:
    """真实大模型决策实现（OpenAI 兼容接口）。

    环境变量：
    - LLM_API_KEY:  API 密钥（必填）
    - LLM_BASE_URL: 接口地址，默认 https://api.openai.com/v1
    - LLM_MODEL:    模型名，默认 gpt-4o-mini
    """

    def __init__(self) -> None:
        self.api_key = os.getenv("LLM_API_KEY", "")
        self.base_url = os.getenv(
            "LLM_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")

    def decide(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """调用真实大模型进行决策，要求返回 JSON。"""
        prompt = (
            "你是内容任务规划 Agent 的决策模块。"
            "可用动作：material_search, script_generator, estimate_cost, switch_plan, "
            "reuse_step, save_plan, finish, block。"
            "请根据当前状态选择下一步动作，只返回 JSON："
            '{"action": 动作名, "params": {}, "rationale": 决策依据, "terminal": false}。'
            f"当前状态：{json.dumps(state, ensure_ascii=False)}"
        )
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            body = json.loads(response.read().decode("utf-8"))
        decision = json.loads(body["choices"][0]["message"]["content"])
        decision.setdefault("params", {})
        decision.setdefault("terminal", False)
        return decision


def build_llm() -> tuple[Any, str]:
    """构建决策模型：配置 LLM_API_KEY 时用 RealLLM，否则用离线 MockLLM。"""
    if os.getenv("LLM_API_KEY"):
        return RealLLM(), "RealLLM"
    return MockLLM(), "MockLLM"
