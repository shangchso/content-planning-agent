"""内容任务规划 Agent 单元测试。

覆盖笔试全部验收点：正常完成、缺预算/截止时间、工具失败、预算超限、
重复执行，以及失败续跑加分项、任务不存在、步数上限等补充场景。

运行命令：
    python -m unittest discover -s tests
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# 保证从项目根目录运行时能导入 src 包
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.agent import ContentPlanningAgent
from src.data_store import DataStore
from src.llm import MockLLM


class ContentPlanningAgentTest(unittest.TestCase):
    """Agent 重规划循环测试。"""

    def setUp(self) -> None:
        self.store = DataStore(PROJECT_ROOT / "data")
        self.llm = MockLLM()

    def _run(self, task_id: str, max_steps: int = 10) -> dict:
        agent = ContentPlanningAgent(
            self.store,
            llm=self.llm,
            llm_name="MockLLM",
            max_steps=max_steps,
        )
        return agent.run(task_id)

    def test_normal_completion_with_replan(self) -> None:
        """正常完成：初始方案超预算，重规划到替代方案后保存。"""
        result = self._run("T01")
        self.assertEqual(result["review_status"], "completed")
        self.assertEqual(result["selected_plan"], "standard")
        self.assertEqual(result["total_cost"], 8)
        self.assertTrue(result["plan_saved"])
        self.assertEqual(result["replan_count"], 1)
        self.assertEqual(result["step_status"]["material_search"], "success")
        self.assertEqual(result["step_status"]["script_generator"], "success")

    def test_missing_budget_blocked(self) -> None:
        """缺预算：阻断且不执行任何步骤。"""
        result = self._run("T02")
        self.assertEqual(result["review_status"], "blocked")
        self.assertIn("budget", result["unfinished_reason"])
        self.assertFalse(result["plan_saved"])
        self.assertEqual(result["step_status"]["material_search"], "not_executed")

    def test_missing_deadline_blocked(self) -> None:
        """缺截止时间：阻断。"""
        result = self._run("T03")
        self.assertEqual(result["review_status"], "blocked")
        self.assertIn("deadline", result["unfinished_reason"])

    def test_no_feasible_plan_blocked(self) -> None:
        """预算超限且无可行方案：返回缺口，不保存。"""
        result = self._run("T04")
        self.assertEqual(result["review_status"], "blocked")
        self.assertIn("缺口", result["unfinished_reason"])
        self.assertFalse(result["plan_saved"])
        self.assertEqual(result["replan_count"], 1)

    def test_fail_once_then_recover(self) -> None:
        """工具一次性失败后切换方案，复用成功步骤并最终完成（加分项）。"""
        self.store.failed_tool_once = "script_generator"
        result = self._run("T01")
        self.assertEqual(result["review_status"], "completed")
        self.assertEqual(result["selected_plan"], "standard")
        self.assertTrue(result["plan_saved"])
        # 素材检索结果被保留复用，没有重复执行
        self.assertEqual(result["step_status"]["material_search"], "success")

    def test_persistent_tool_failure_blocked(self) -> None:
        """工具持续失败且无替代方案：阻断，不把失败记为成功。"""
        self.store.failed_tool = "script_generator"
        result = self._run("T01")
        self.assertEqual(result["review_status"], "blocked")
        self.assertFalse(result["plan_saved"])
        self.assertEqual(result["step_status"]["script_generator"], "not_executed")

    def test_repeated_execution_is_idempotent(self) -> None:
        """重复执行：第二次保存命中幂等，不产生新方案。"""
        first = self._run("T05")
        self.assertTrue(first["plan_saved"])
        self.assertFalse(first["duplicated_execution"])

        second = self._run("T05")
        self.assertEqual(second["review_status"], "completed")
        self.assertTrue(second["duplicated_execution"])
        self.assertEqual(len(self.store.list_saved_plans()), 1)

    def test_nonexistent_task_blocked(self) -> None:
        """任务不存在：阻断。"""
        result = self._run("NO_SUCH_TASK")
        self.assertEqual(result["review_status"], "blocked")
        self.assertIn("任务不存在", result["unfinished_reason"])

    def test_step_limit_returns_incomplete(self) -> None:
        """步数上限：设置极小步数时返回明确未完成状态。"""
        result = self._run("T01", max_steps=1)
        self.assertEqual(result["review_status"], "incomplete")
        self.assertIn("最大步数", result["unfinished_reason"])


if __name__ == "__main__":
    unittest.main()
