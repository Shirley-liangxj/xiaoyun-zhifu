"""Agent 离线控制层评测 Schema。"""
from pydantic import BaseModel


class AgentEvalResult(BaseModel):
  id: str
  input: str
  tool_sequence: list[str] = []
  parameter_ok: bool
  high_risk_blocked: bool
  need_human: bool
  should_ask_followup: bool
  terminal_state: str
  risk_level: str = ""
  reason: str = ""
  trajectory: dict = {}
  failure_reason: str | None = None
  passed: bool


class AgentEvalReport(BaseModel):
  total: int
  execution_mode: str
  tool_sequence_accuracy: float
  parameter_accuracy: float
  followup_accuracy: float
  terminal_state_accuracy: float
  high_risk_missed_count: int
  false_transfer_count: int
  end_to_end_success_rate: float
  failures: list[dict] = []
  results: list[AgentEvalResult] = []
  message: str
