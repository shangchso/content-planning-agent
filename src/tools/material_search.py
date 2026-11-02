"""工具一：素材检索。

按任务主题检索可用素材，返回素材列表及本步骤在当前方案下的费用与耗时。
通过 store.failed_tool 注入失败时返回 ok=False。
"""

from __future__ import annotations

from typing import Any, Dict

from ..data_store import DataStore


def search_material(store: DataStore, task: Dict[str, Any], plan: str) -> Dict[str, Any]:
    """检索素材。

    Args:
        store: 数据仓库。
        task: 任务数据。
        plan: 当前方案名。

    Returns:
        统一结构的工具返回结果。
    """
    tool = "material_search"
    arguments = {"theme": task["theme"], "plan": plan}

    if store.is_tool_failed(tool):
        return {
            "ok": False,
            "tool": tool,
            "arguments": arguments,
            "error": "素材检索服务执行失败",
        }

    materials = store.get_materials(task["theme"])
    meta = store.get_tool_meta(tool, plan)

    return {
        "ok": True,
        "tool": tool,
        "arguments": arguments,
        "result": {
            "materials": materials,
            "material_count": len(materials),
            "step_cost": meta["cost"],
            "step_duration": meta["duration"],
        },
    }
