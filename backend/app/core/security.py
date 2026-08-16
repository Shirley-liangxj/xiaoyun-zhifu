"""安全模块 - JWT 令牌与密码处理"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings


def hash_password(password: str) -> str:
  """将明文密码哈希"""
  return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
  """验证明文密码与哈希是否匹配"""
  return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
  """生成 JWT 访问令牌"""
  to_encode = data.copy()
  expire = datetime.now(timezone.utc) + (
    expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
  )
  to_encode.update({"exp": expire})
  return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict]:
  """解码 JWT 令牌，失败返回 None"""
  try:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
  except JWTError:
    return None
