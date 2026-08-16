"""路由包"""
from app.routers import auth, conversations, knowledge, stats, tickets, users

__all__ = ["auth", "users", "conversations", "tickets", "knowledge", "stats"]
