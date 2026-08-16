"""数据统计 Schema"""
from pydantic import BaseModel


class OverviewStats(BaseModel):
  """总览统计"""
  total_conversations: int = 0
  active_conversations: int = 0
  total_messages: int = 0
  total_tickets: int = 0
  open_tickets: int = 0
  in_progress_tickets: int = 0
  resolved_tickets: int = 0
  total_knowledge_docs: int = 0
  indexed_docs: int = 0
  ai_suggestions: int = 0
  ai_accepted: int = 0
  ai_accept_rate: float = 0.0


class TicketStatusBreakdown(BaseModel):
  """工单状态分布"""
  open: int = 0
  in_progress: int = 0
  resolved: int = 0
  closed: int = 0


class PriorityBreakdown(BaseModel):
  """工单优先级分布"""
  low: int = 0
  normal: int = 0
  high: int = 0
  urgent: int = 0


class DashboardStats(BaseModel):
  """Dashboard 完整统计数据"""
  overview: OverviewStats
  ticket_status: TicketStatusBreakdown
  ticket_priority: PriorityBreakdown
