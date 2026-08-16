"""路由包"""
from app.routers import auth, conversations, eval, knowledge, public_chat, quick_replies, settings, stats, tickets, users

__all__ = ["auth", "users", "conversations", "tickets", "knowledge", "stats", "eval", "settings", "public_chat", "quick_replies"]
