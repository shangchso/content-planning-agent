"""内存数据存储层。

负责加载 data/ 目录下的合成数据（任务、工具费用耗时、素材库），
并在运行期间维护步骤结果与已保存方案。所有数据仅保存在内存中。

提供 failed_tool 注入开关，用于模拟指定工具执行失败。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


class DataStore:
    """基于 JSON 文件的内存数据仓库。"""

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._materials: List[Dict[str, Any]] = []
        self._tool_config: Dict[str, Any] = {}
        # 已保存方案：key 为任务 ID，value 为方案记录。同一任务只保留一份。
        self._saved_plans: Dict[str, Dict[str, Any]] = {}
        # 失败注入：指定工具名后，该工具执行时始终返回失败。
        self.failed_tool: Optional[str] = None
        # 一次性失败注入：该工具下一次调用失败，之后自动恢复，用于失败续跑。
        self.failed_tool_once: Optional[str] = None
        self.load()

    def load(self) -> None:
        """从 JSON 文件加载全部基础数据。"""
        with (self.data_dir / "tasks.json").open("r", encoding="utf-8") as f:
            task_data = json.load(f)
        for task in task_data["tasks"]:
            self._tasks[task["task_id"]] = task

        with (self.data_dir / "materials.json").open("r", encoding="utf-8") as f:
            material_data = json.load(f)
        self._materials = material_data["materials"]

        with (self.data_dir / "tools.json").open("r", encoding="utf-8") as f:
            self._tool_config = json.load(f)

    # ---------- 任务相关 ----------
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """按 ID 获取任务，不存在返回 None。"""
        return self._tasks.get(task_id)

    # ---------- 素材相关 ----------
    def get_materials(self, theme: str) -> List[Dict[str, Any]]:
        """按主题获取可用素材。"""
        return [
            material
            for material in self._materials
            if material["theme"] == theme and material["available"]
        ]

    # ---------- 方案与工具配置 ----------
    def get_plan_order(self) -> List[str]:
        """获取方案尝试顺序（初始方案在前，替代方案在后）。"""
        return list(self._tool_config["plan_order"])

    def get_plan_steps(self, plan: str) -> List[str]:
        """获取某方案包含的执行步骤（工具名顺序）。"""
        return list(self._tool_config["plan_steps"][plan])

    def get_plan_display_name(self, plan: str) -> str:
        """获取方案中文名称。"""
        return self._tool_config["plan_display_name"][plan]

    def get_tool_display_name(self, tool: str) -> str:
        """获取工具中文名称。"""
        return self._tool_config["tools"][tool]["display_name"]

    def get_tool_meta(self, tool: str, plan: str) -> Dict[str, int]:
        """获取某工具在指定方案下的费用与耗时。"""
        return self._tool_config["tools"][tool]["plans"][plan]

    def is_tool_failed(self, tool: str) -> bool:
        """判断该工具是否被注入失败。

        一次性失败命中后立即清除，保证后续调用恢复成功（失败续跑）。
        """
        if self.failed_tool_once == tool:
            self.failed_tool_once = None
            return True
        return self.failed_tool == tool

    # ---------- 方案保存 ----------
    def has_saved_plan(self, task_id: str) -> bool:
        """判断任务是否已保存方案。"""
        return task_id in self._saved_plans

    def get_saved_plan(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务已保存的方案。"""
        return self._saved_plans.get(task_id)

    def save_plan_record(self, plan_record: Dict[str, Any]) -> Dict[str, Any]:
        """保存方案，幂等：同一任务重复保存不新建，返回 duplicated=True。"""
        task_id = plan_record["task_id"]
        if task_id in self._saved_plans:
            return {
                "ok": True,
                "duplicated": True,
                "plan": self._saved_plans[task_id],
                "message": "该任务已保存方案，重复执行未产生新方案",
            }
        self._saved_plans[task_id] = plan_record
        return {
            "ok": True,
            "duplicated": False,
            "plan": plan_record,
            "message": "方案保存成功",
        }

    def list_saved_plans(self) -> List[Dict[str, Any]]:
        """列出全部已保存方案。"""
        return list(self._saved_plans.values())

    def reset_runtime(self) -> None:
        """清空运行期方案并关闭失败注入。"""
        self._saved_plans.clear()
        self.failed_tool = None
        self.failed_tool_once = None
