"""Exercise local checks; deliberately stop before evidence/model execution."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from _core import load_json, validate_bundle, search_plan, write_json

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="A NEW directory, never overwritten")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Run directory already exists; choose a new directory")
    args.out.mkdir(parents=True)
    check = validate_bundle(ROOT / "examples/minimal-demo/task.json")
    plan = search_plan(load_json(ROOT / "registry/seed_candidates.json"), "literature")
    write_json(args.out / "input_check.json", check)
    write_json(args.out / "skill_search_plan.json", plan)
    state = {"mode": "offline_demo", "data_kind": "synthetic_demo", "stage": "literature",
             "status": "needs_evidence_and_model" if check["valid"] else "blocked_invalid_inputs",
             "executed": ["validate_inputs", "prepare_offline_skill_search_plan"],
             "not_executed": ["live_github_search", "external_skill_execution", "literature_retrieval",
                              "llm_invocation", "numerical_process_prediction", "optimisation", "physical_printing"],
             "input_hashes": check["input_hashes"],
             "next_step": "Compare and approve a literature workflow in the selected host; retrieve source-grounded evidence."}
    write_json(args.out / "run_state.json", state)
    events = [
        {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "event": "local_input_check", "status": check["status"]},
        {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "event": "search_plan_prepared", "live_search": False},
        {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "event": "stopped", "status": state["status"]},
    ]
    (args.out / "events.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in events) + "\n", encoding="utf-8")
    summary = f"""# v0.1 本地起步演示\n\n**仅合成软件测试数据，不是打印结果。**\n\n- 输入检查：{'通过' if check['valid'] else '未通过'}；{check.get('n_rows', 0)}行。\n- 完成：本地格式检查、离线文献子Skill检索计划、运行状态与日志。\n- 未完成：在线检索、调用外部Skill、模型计算、参数优化、真实打印。\n- 当前状态：`{state['status']}`。\n\n下一步应核查并运行文献流程，不能由本示例推断参数优化效果。\n"""
    (args.out / "summary.md").write_text(summary, encoding="utf-8")
    print(f"Starter demo complete: {args.out.resolve()}")
    print(f"Status: {state['status']}; no external skill or scientific model was executed.")
    return 0 if check["valid"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
