"""Agent 核心：ReAct 决策与重规划循环。

循环结构（笔试硬性要求）：
    模型选择动作 → 执行工具 → 观察结果 → 模型调整下一步或结束

本项目额外体现重规划能力：
- 工具失败或成本超预算时切换替代方案；
- 已成功步骤的结果保留，切换方案后可复用，不重复执行（失败续跑）；
- max_steps 限制步数，超限返回明确的未完成状态。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import tools
from .data_store import DataStore
from .llm import MockLLM


def _summarize(tool_name: str, response: Optional[Dict[str, Any]]) -> str:
    """把工具返回压缩为简短观察摘要。"""
    if response is None:
        return f"{tool_name} 状态更新完成"
    if not response.get("ok", True):
        return f"{tool_name} 返回失败：{response.get('error')}"
    result = response.get("result", {})
    keys = (
        "material_count",
        "script_summary",
        "step_cost",
        "total_cost",
        "total_duration",
        "within_budget",
        "budget_gap",
        "duplicated",
        "message",
    )
    summary = {key: result[key] for key in keys if key in result}
    return f"{tool_name} 返回：{summary}"


class ContentPlanningAgent:
    """内容任务规划 Agent。"""

    def __init__(
        self,
        store: DataStore,
        llm: Optional[Any] = None,
        llm_name: str = "MockLLM",
        max_steps: int = 10,
    ) -> None:
        self.store = store
        self.llm = llm or MockLLM()
        self.llm_name = llm_name
        self.max_steps = max_steps

    def run(self, task_id: str) -> Dict[str, Any]:
        """对单个任务执行完整 ReAct 重规划循环。"""
        state = self._initial_state(task_id)
        trace: List[Dict[str, Any]] = []
        terminal_action: Optional[str] = None
        terminal_reason = ""

        for step in range(1, self.max_steps + 1):
            decision = self.llm.decide(state)
            action = decision["action"]
            params = decision.get("params", {})

            if action in ("block", "finish"):
                terminal_action = action
                terminal_reason = params.get("reason", decision.get("rationale", ""))
                trace.append(
                    {
                        "step": step,
                        "action": action,
                        "tool_arguments": params,
                        "observation_summary": f"终结动作：{decision['rationale']}",
                        "decision_rationale": decision["rationale"],
                    }
                )
                break

            response = self._execute(action, params, state)
            self._update_state(action, params, response, state)
            trace.append(
                {
                    "step": step,
                    "action": action,
                    "tool_arguments": response.get("arguments", params)
                    if response
                    else params,
                    "observation_summary": _summarize(action, response),
                    "decision_rationale": decision["rationale"],
                }
            )
        else:
            terminal_action = "step_limit"
            terminal_reason = f"达到最大步数 {self.max_steps}，任务未完成"

        return self._build_result(state, trace, terminal_action, terminal_reason)

    # ---------- 初始状态 ----------
    def _initial_state(self, task_id: str) -> Dict[str, Any]:
        task = self.store.get_task(task_id)
        plan_order = self.store.get_plan_order()

        state: Dict[str, Any] = {
            "task_id": task_id,
            "task": task,
            "task_missing": task is None,
            "missing_inputs": [],
            "plan_order": plan_order,
            "plan_index": 0,
            "current_plan": plan_order[0],
            "plan_steps": self.store.get_plan_steps(plan_order[0]),
            "current_step_index": 0,
            "completed_steps": {},
            "cost_result": None,
            "need_replan": False,
            "replan_reason": None,
            "has_alternative_plan": len(plan_order) > 1,
            "replan_count": 0,
            "save_done": False,
            "save_ok": False,
            "duplicated": False,
        }

        if task is not None:
            missing: List[str] = []
            if task.get("budget") is None:
                missing.append("budget")
            if task.get("deadline") is None:
                missing.append("deadline")
            state["missing_inputs"] = missing

        return state

    # ---------- 动作执行 ----------
    def _execute(
        self, action: str, params: Dict[str, Any], state: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """根据决策动作调用对应工具；纯状态动作返回 None。"""
        task = state["task"]
        plan = params.get("plan", state["current_plan"])

        if action == "material_search":
            return tools.search_material(self.store, task, plan)

        if action == "script_generator":
            materials = state["completed_steps"]["material_search"]["result"]["materials"]
            return tools.generate_script(self.store, task, plan, materials)

        if action == "estimate_cost":
            return tools.estimate_cost(self.store, task, plan)

        if action == "save_plan":
            cost_result = state["cost_result"]
            script_summary = state["completed_steps"]["script_generator"]["result"][
                "script_summary"
            ]
            return tools.save_plan(
                self.store, task, plan, cost_result, script_summary
            )

        # switch_plan / reuse_step 为纯状态动作，不调用工具
        return None

    # ---------- 状态更新 ----------
    def _update_state(
        self,
        action: str,
        params: Dict[str, Any],
        response: Optional[Dict[str, Any]],
        state: Dict[str, Any],
    ) -> None:
        """根据观察结果更新状态，供下一轮决策使用。"""
        if action == "material_search":
            if response["ok"]:
                state["completed_steps"]["material_search"] = {
                    "plan": state["current_plan"],
                    "result": response["result"],
                }
                state["current_step_index"] += 1
            else:
                state["need_replan"] = True
                state["replan_reason"] = response["error"]
            return

        if action == "script_generator":
            if response["ok"]:
                state["completed_steps"]["script_generator"] = {
                    "plan": state["current_plan"],
                    "result": response["result"],
                }
                state["current_step_index"] += 1
            else:
                state["need_replan"] = True
                state["replan_reason"] = response["error"]
            return

        if action == "reuse_step":
            state["current_step_index"] += 1
            return

        if action == "estimate_cost":
            state["cost_result"] = response["result"]
            return

        if action == "switch_plan":
            self._apply_switch_plan(params, state)
            return

        if action == "save_plan":
            result = response["result"]
            state["save_done"] = True
            state["save_ok"] = result["ok"]
            state["duplicated"] = result.get("duplicated", False)
            return

    def _apply_switch_plan(
        self, params: Dict[str, Any], state: Dict[str, Any]
    ) -> None:
        """执行重规划：切换方案并重置方案内步骤，保留已成功步骤。"""
        new_plan = params["to"]
        state["replan_count"] += 1
        state["plan_index"] = state["plan_order"].index(new_plan)
        state["current_plan"] = new_plan
        state["plan_steps"] = self.store.get_plan_steps(new_plan)
        state["current_step_index"] = 0
        state["cost_result"] = None
        state["need_replan"] = False
        state["replan_reason"] = None
        state["has_alternative_plan"] = (
            state["plan_index"] < len(state["plan_order"]) - 1
        )

        # material_search 与方案无关，跨方案保留；script_generator 绑定方案，
        # 切换后移除，要求按新方案重新生成。
        if "script_generator" in state["completed_steps"]:
            if state["completed_steps"]["script_generator"]["plan"] != new_plan:
                del state["completed_steps"]["script_generator"]

    # ---------- 结果组装 ----------
    def _build_result(
        self,
        state: Dict[str, Any],
        trace: List[Dict[str, Any]],
        terminal_action: str,
        terminal_reason: str,
    ) -> Dict[str, Any]:
        """组装最终交付结果。"""
        status_map = {
            "finish": "completed",
            "block": "blocked",
            "step_limit": "incomplete",
        }
        review_status = status_map.get(terminal_action, "incomplete")

        step_status = {
            tool: (
                "success"
                if tool in state["completed_steps"]
                else "not_executed"
            )
            for tool in ("material_search", "script_generator")
        }

        cost = state["cost_result"]
        total_cost = cost["total_cost"] if cost else None
        total_duration = cost["total_duration"] if cost else None

        return {
            "task_id": state["task_id"],
            "review_status": review_status,
            "selected_plan": state["current_plan"],
            "plan_display_name": self.store.get_plan_display_name(
                state["current_plan"]
            ),
            "step_status": step_status,
            "total_cost": total_cost,
            "total_duration": total_duration,
            "plan_saved": state["save_ok"],
            "duplicated_execution": state["duplicated"],
            "replan_count": state["replan_count"],
            "unfinished_reason": terminal_reason
            if review_status != "completed"
            else "",
            "steps_used": len(trace),
            "llm_name": self.llm_name,
            "trace": trace,
        }
