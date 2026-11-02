"""命令行入口（CLI 运行方式）。

可复制的运行命令示例：
    # 查看全部任务
    python run.py --list

    # 正常完成（初始方案超预算，自动重规划到替代方案后保存）
    python run.py --task T01 --tag normal

    # 缺预算 / 缺截止时间
    python run.py --task T02 --tag missing_budget
    python run.py --task T03 --tag missing_deadline

    # 工具失败（注入脚本生成失败，重规划且保留已成功的素材检索结果）
    python run.py --task T01 --fail-tool script_generator --tag tool_fail

    # 预算超限且无可行方案
    python run.py --task T04 --tag no_feasible

    # 重复执行（同一任务连续两次，验证幂等）
    python run.py --task T05 --repeat 2
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

from src.agent import ContentPlanningAgent
from src.data_store import DataStore
from src.llm import build_llm


def print_json(obj: Dict[str, Any]) -> None:
    """以可读 JSON 格式输出。"""
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def list_tasks(store: DataStore) -> None:
    """列出全部任务摘要。"""
    tasks_path = Path(store.data_dir) / "tasks.json"
    with tasks_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    print("可用任务列表：")
    for task in data["tasks"]:
        print(
            f"  - {task['task_id']}: theme={task['theme']}, "
            f"budget={task['budget']}, deadline={task['deadline']}"
        )


def save_trace(
    result: Dict[str, Any], trace_dir: Path, tag: str | None
) -> Path:
    """把结果与 Trace 落盘到 examples/traces/。"""
    trace_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_{tag}" if tag else ""
    trace_path = trace_dir / f"trace_{result['task_id']}{suffix}.json"
    with trace_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return trace_path


def parse_args(argv: List[str]) -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="内容任务规划 Agent（CLI）")
    parser.add_argument("--task", "-t", help="待处理任务 ID，如 T01")
    parser.add_argument("--data-dir", default="data", help="数据目录，默认 data")
    parser.add_argument(
        "--fail-tool",
        choices=["material_search", "script_generator"],
        help="向指定工具注入持续失败",
    )
    parser.add_argument(
        "--fail-tool-once",
        choices=["material_search", "script_generator"],
        help="向指定工具注入一次性失败（下一次调用失败，之后恢复，用于失败续跑）",
    )
    parser.add_argument("--max-steps", type=int, default=10, help="最大步数，默认 10")
    parser.add_argument("--repeat", type=int, default=1, help="连续运行次数，默认 1")
    parser.add_argument("--tag", default=None, help="Trace 文件名后缀")
    parser.add_argument(
        "--trace-dir", default="examples/traces", help="Trace 目录，默认 examples/traces"
    )
    parser.add_argument("--list", action="store_true", help="列出全部任务后退出")
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    """主流程。"""
    args = parse_args(argv if argv is not None else sys.argv[1:])
    store = DataStore(args.data_dir)

    if args.list:
        list_tasks(store)
        return 0

    if not args.task:
        print("错误：请通过 --task 指定任务 ID，或使用 --list 查看任务", file=sys.stderr)
        return 2

    if args.fail_tool:
        store.failed_tool = args.fail_tool
    if args.fail_tool_once:
        store.failed_tool_once = args.fail_tool_once

    llm, llm_name = build_llm()

    for run_index in range(args.repeat):
        agent = ContentPlanningAgent(
            store,
            llm=llm,
            llm_name=llm_name,
            max_steps=args.max_steps,
        )
        result = agent.run(args.task)

        tag = args.tag
        if args.repeat > 1:
            tag = f"{tag or 'repeat'}_{run_index + 1}"
        trace_path = save_trace(result, Path(args.trace_dir), tag)
        print(f"===== 第 {run_index + 1} 次运行结果（Trace：{trace_path}）=====")
        print_json(result)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
