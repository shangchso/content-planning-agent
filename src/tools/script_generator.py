"""工具二：脚本生成。

基于检索到的素材生成活动脚本，返回脚本摘要及本步骤在当前方案下的
费用与耗时。支持失败注入。
"""

from __future__ import annotations

from typing import Any, Dict, List

from ..data_store import DataStore


def generate_script(
    store: DataStore,
    task: Dict[str, Any],
    plan: str,
    materials: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """生成活动脚本。

    Args:
        store: 数据仓库。
        task: 任务数据。
        plan: 当前方案名。
        materials: 上一步检索到的素材列表。

    Returns:
        统一结构的工具返回结果。
    """
    tool = "script_generator"
    arguments = {"task_id": task["task_id"], "plan": plan}

    if store.is_tool_failed(tool):
        return {
            "ok": False,
            "tool": tool,
            "arguments": arguments,
            "error": "脚本生成工具执行失败",
        }

    meta = store.get_tool_meta(tool, plan)
    material_titles = [material["title"] for material in materials]
    script_summary = (
        f"基于 {len(materials)} 个素材生成《{task['theme']}》活动脚本，"
        f"引用素材：{material_titles}"
    )

    return {
        "ok": True,
        "tool": tool,
        "arguments": arguments,
        "result": {
            "script_summary": script_summary,
            "step_cost": meta["cost"],
            "step_duration": meta["duration"],
        },
    }
