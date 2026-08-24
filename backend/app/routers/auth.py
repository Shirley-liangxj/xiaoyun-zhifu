"""认证路由 - 注册与登录"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.models import Company, User
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.services.bootstrap import seed_minimal_demo, seed_tenant_defaults

router = APIRouter(prefix="/api/auth", tags=["认证"])


@router.post("/register", response_model=TokenResponse, summary="注册新账号")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
  """
  注册流程：
  1. 创建公司（租户）
  2. 创建管理员用户
  3. 返回 JWT 令牌
  """
  # 检查用户名/邮箱是否已存在
  if db.query(User).filter(User.username == body.username).first():
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
  if db.query(User).filter(User.email == body.email).first():
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")

  # 创建公司
  company = Company(name=body.company_name)
  db.add(company)
  db.flush()  # 获取 company.id

  # 创建用户（首个用户为 admin）
  user = User(
    username=body.username,
    email=body.email,
    hashed_password=hash_password(body.password),
    display_name=body.display_name or body.username,
    role="admin",
    company_id=company.id,
  )
  db.add(user)
  db.commit()
  db.refresh(user)
  seed_tenant_defaults(db, company.id)
  seed_minimal_demo(db, company.id, user.id)

  token = create_access_token({"sub": str(user.id)})
  return TokenResponse(access_token=token)


@router.post("/login", response_model=TokenResponse, summary="用户登录")
def login(body: LoginRequest, db: Session = Depends(get_db)):
  """验证用户名密码，返回 JWT 令牌"""
  user = db.query(User).filter(User.username == body.username).first()
  if not user or not verify_password(body.password, user.hashed_password):
    raise HTTPException(
      status_code=status.HTTP_401_UNAUTHORIZED,
      detail="用户名或密码错误",
    )
  if not user.is_active:
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")

  token = create_access_token({"sub": str(user.id)})
  return TokenResponse(access_token=token)
