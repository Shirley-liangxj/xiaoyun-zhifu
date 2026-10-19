"""Agent 主循环离线评测：mock 外部边界，真实运行控制流和数据库状态。"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agent import agent_loop
from app.agent.intent_router import detect_high_risk
from app.agent.tool_registry import run_tool as registry_run_tool
from app.database import Base
from app.models import Company
from app.services.errors import ExternalServiceError
from app.services.llm import LLMResult

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _resolve_eval_dir(project_root: Path, container_eval: Path = Path("/app/eval")) -> Path:
  """Docker 优先读取持久卷内评测集，本机开发回退到项目根目录。"""
  return container_eval if container_eval.exists() else project_root / "eval"


EVAL_DIR = _resolve_eval_dir(PROJECT_ROOT)
CASES_FILE = EVAL_DIR / "agent_cases.json"


def load_agent_cases() -> list[dict]:
  if not CASES_FILE.exists():
    return []
  with CASES_FILE.open(encoding="utf-8") as f:
    data = json.load(f)
  return data.get("cases", [])


def _args_match(expected: dict, actual: dict) -> bool:
  """允许 fixture 用 null 表示“未提供”，不把工具默认值误算成参数抽取。"""
  for key, value in expected.items():
    if value is None:
      if actual.get(key) not in (None, ""):
        return False
    elif actual.get(key) != value:
      return False
  return True


def _scripted_complete(steps: list[dict]):
  queue = iter(steps)

  def complete(*_args, **_kwargs):
    try:
      step = next(queue)
    except StopIteration as exc:
      raise ExternalServiceError("mock LLM 脚本已耗尽") from exc
    if step.get("error"):
      raise ExternalServiceError(step["error"])
    tool_calls = [
      {
        "id": f"eval-call-{index}",
        "type": "function",
        "function": {
          "name": call["name"],
          "arguments": json.dumps(call.get("arguments", {}), ensure_ascii=False),
        },
      }
      for index, call in enumerate(step.get("tool_calls", []), start=1)
    ]
    return LLMResult(content=step.get("content", ""), tool_calls=tool_calls)

  return complete


def _run_case(case: dict) -> tuple[dict, dict]:
  engine = create_engine("sqlite:///:memory:")
  Base.metadata.create_all(engine)
  db = sessionmaker(bind=engine)()
  db.add(Company(id=1, name="离线评测店铺", industry="服饰"))
  db.commit()
  traces: list[dict] = []
  fixtures = case.get("tool_outputs", {})

  def eval_tool_runner(name: str, message: str, **kwargs):
    if name in fixtures:
      return copy.deepcopy(fixtures[name])
    return registry_run_tool(name, message, **kwargs)

  try:
    with (
      patch.object(agent_loop.llm_service, "complete", side_effect=_scripted_complete(case.get("llm_steps", []))),
      patch.object(agent_loop, "run_tool", side_effect=eval_tool_runner),
      patch.object(agent_loop, "append_trace", side_effect=lambda record: traces.append(copy.deepcopy(record))),
    ):
      result = agent_loop.run_agent_turn(
        db,
        1,
        case.get("input", ""),
        customer_name="离线评测买家",
      )
    trace = traces[-1] if traces else {}
    return result, trace
  finally:
    db.close()
    engine.dispose()


def run_agent_evaluation() -> dict:
  cases = load_agent_cases()
  failures: list[dict] = []
  sequence_ok = 0
  parameter_total = 0
  parameter_ok = 0
  followup_ok = 0
  terminal_ok = 0
  high_risk_missed = 0
  false_transfer = 0
  end_to_end_ok = 0
  results: list[dict] = []

  for case in cases:
    expected_tools = case.get("expected_tools", [])
    expected_args = case.get("expected_args", [])
    expected = case.get("expected", {})
    result, trace = _run_case(case)
    actual_tools = [item.get("name", "") for item in trace.get("tools", [])]
    actual_args = [item.get("args") or {} for item in trace.get("tools", [])]
    high_risk = trace.get("source") == "high_risk_regex"
    need_human = bool(result.get("need_human"))
    terminal_state = result.get("terminal_state", "")
    asked_followup = terminal_state == "needs_clarification"

    seq_pass = actual_tools == expected_tools
    if seq_pass:
      sequence_ok += 1
    else:
      failures.append({"id": case.get("id"), "type": "tool_sequence", "expected": expected_tools, "actual": actual_tools})

    args_pass = len(actual_args) == len(expected_args)
    if args_pass:
      for exp, act in zip(expected_args, actual_args):
        if not _args_match(exp, act):
          args_pass = False
          break
    parameter_total += max(len(expected_args), len(actual_args))
    parameter_ok += sum(
      _args_match(exp, act) for exp, act in zip(expected_args, actual_args)
    )
    if not args_pass:
      failures.append({"id": case.get("id"), "type": "parameters", "expected": expected_args, "actual": actual_args})

    expected_followup = bool(case.get("should_ask_followup"))
    followup_pass = asked_followup == expected_followup
    if followup_pass:
      followup_ok += 1
    else:
      failures.append({"id": case.get("id"), "type": "followup", "expected": expected_followup, "actual": asked_followup})

    expected_terminal = case.get("expected_terminal_state")
    terminal_pass = terminal_state == expected_terminal
    if terminal_pass:
      terminal_ok += 1
    else:
      failures.append({"id": case.get("id"), "type": "terminal_state", "expected": expected_terminal, "actual": terminal_state})

    if expected.get("high_risk_blocked") and not high_risk:
      high_risk_missed += 1
      failures.append({"id": case.get("id"), "type": "high_risk_missed"})
    if need_human != bool(expected.get("need_human")):
      false_transfer += 1
      failures.append({"id": case.get("id"), "type": "human_branch", "expected": expected.get("need_human"), "actual": need_human})

    case_ok = seq_pass and args_pass and followup_pass and terminal_pass and not (
      expected.get("high_risk_blocked") and not high_risk
    ) and need_human == bool(expected.get("need_human"))
    if case_ok:
      end_to_end_ok += 1
    results.append({
      "id": case.get("id"),
      "input": case.get("input", ""),
      "tool_sequence": actual_tools,
      "parameter_ok": args_pass,
      "high_risk_blocked": high_risk,
      "need_human": need_human,
      "should_ask_followup": asked_followup,
      "terminal_state": terminal_state,
      "risk_level": case.get("risk_level", ""),
      "reason": case.get("reason", ""),
      "trajectory": {
        "tools": trace.get("tools", []),
        "llm_calls": trace.get("llm_calls", 0),
        "interrupt_reason": trace.get("interrupt_reason"),
        "output": trace.get("output", ""),
      },
      "failure_reason": next((f["type"] for f in failures if f.get("id") == case.get("id")), None),
      "passed": case_ok,
    })

  total = len(cases)
  return {
    "total": total,
    "execution_mode": "mock_llm_real_agent_loop",
    "tool_sequence_accuracy": round(sequence_ok / total * 100, 1) if total else 0.0,
    "parameter_accuracy": round(parameter_ok / parameter_total * 100, 1) if parameter_total else 100.0,
    "followup_accuracy": round(followup_ok / total * 100, 1) if total else 0.0,
    "terminal_state_accuracy": round(terminal_ok / total * 100, 1) if total else 0.0,
    "high_risk_missed_count": high_risk_missed,
    "false_transfer_count": false_transfer,
    "end_to_end_success_rate": round(end_to_end_ok / total * 100, 1) if total else 0.0,
    "failures": failures,
    "results": results,
    "message": "mock 外部 LLM/RAG 边界、真实运行 Agent 主循环与数据库状态；结果不等于真实模型线上准确率。",
  }
