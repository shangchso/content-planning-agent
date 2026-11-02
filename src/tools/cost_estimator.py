"""工具三：成本估算。

汇总当前方案全部步骤的费用与耗时，与任务预算对比，返回是否超预算。
估算动作本身不产生费用。
"""

from __future__ import annotations

from typing import Any, Dict

from ..data_store import DataStore


def estimate_cost(store: DataStore, task: Dict[str, Any], plan: str) -> Dict[str, Any]:
    """估算方案总成本。

    Args:
        store: 数据仓库。
        task: 任务数据。
        plan: 当前方案名。

    Returns:
        统一结构的工具返回结果，result 含总费用、总耗时与预算对比。
    """
    steps = store.get_plan_steps(plan)
    total_cost = 0
    total_duration = 0
    step_breakdown = {}

    for tool in steps:
        meta = store.get_tool_meta(tool, plan)
        total_cost += meta["cost"]
        total_duration += meta["duration"]
        step_breakdown[tool] = meta

    budget = task["budget"]
    within_budget = total_cost <= budget

    return {
        "ok": True,
        "tool": "cost_estimator",
        "arguments": {"task_id": task["task_id"], "plan": plan},
        "result": {
            "plan": plan,
            "plan_display_name": store.get_plan_display_name(plan),
            "steps": steps,
            "step_breakdown": step_breakdown,
            "total_cost": total_cost,
            "total_duration": total_duration,
            "budget": budget,
            "within_budget": within_budget,
            "budget_gap": budget - total_cost,
        },
    }
