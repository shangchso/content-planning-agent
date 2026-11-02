"""工具四：方案保存。

将最终方案记录保存到仓库，具备幂等性：同一任务重复执行只保留一份方案。
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..data_store import DataStore


def save_plan(
    store: DataStore,
    task: Dict[str, Any],
    plan: str,
    cost_result: Dict[str, Any],
    script_summary: str,
) -> Dict[str, Any]:
    """保存方案。

    Args:
        store: 数据仓库。
        task: 任务数据。
        plan: 最终采用的方案名。
        cost_result: 成本估算结果（result 部分）。
        script_summary: 脚本摘要。

    Returns:
        统一结构的工具返回结果。
    """
    plan_record = {
        "task_id": task["task_id"],
        "theme": task["theme"],
        "selected_plan": plan,
        "plan_display_name": store.get_plan_display_name(plan),
        "script_summary": script_summary,
        "total_cost": cost_result["total_cost"],
        "total_duration": cost_result["total_duration"],
        "budget": task["budget"],
        "deadline": task["deadline"],
    }

    save_result = store.save_plan_record(plan_record)

    return {
        "ok": True,
        "tool": "plan_saver",
        "arguments": {"task_id": task["task_id"], "plan": plan},
        "result": save_result,
    }
