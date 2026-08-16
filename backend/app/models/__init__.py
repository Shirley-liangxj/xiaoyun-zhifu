"""模型包 - 统一导出所有 ORM 模型"""
from app.models.company import Company
from app.models.company_settings import CompanySettings
from app.models.conversation import Conversation, Message
from app.models.knowledge import KnowledgeDoc
from app.models.knowledge_gap import KnowledgeGap
from app.models.quick_reply import QuickReply
from app.models.ticket import Ticket
from app.models.user import User

__all__ = [
  "Company",
  "CompanySettings",
  "User",
  "KnowledgeDoc",
  "KnowledgeGap",
  "QuickReply",
  "Conversation",
  "Message",
  "Ticket",
]
