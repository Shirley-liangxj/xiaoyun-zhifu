"""依赖注入 - 获取当前登录用户"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.database import get_db
from app.models import User

security = HTTPBearer()


def get_current_user(
  credentials: HTTPAuthorizationCredentials = Depends(security),
  db: Session = Depends(get_db),
) -> User:
  """从 JWT 令牌解析并返回当前用户"""
  token = credentials.credentials
  payload = decode_access_token(token)
  if payload is None:
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="令牌无效或已过期",
      headers={"WWW-Authenticate": "Bearer"},
    )

  user_id: Optional[int] = payload.get("sub")
  if user_id is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="令牌格式错误")

  user = db.query(User).filter(User.id == int(user_id), User.is_active == True).first()
  if user is None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在或已禁用")

  return user
