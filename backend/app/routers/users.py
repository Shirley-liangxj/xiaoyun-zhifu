"""用户路由"""
from fastapi import APIRouter, Depends

from app.deps import get_current_user
from app.models import User
from app.schemas.auth import UserResponse

router = APIRouter(prefix="/api/users", tags=["用户"])


@router.get("/me", response_model=UserResponse, summary="获取当前用户信息")
def get_me(current_user: User = Depends(get_current_user)):
  """返回当前登录用户的详细信息"""
  company = current_user.company
  return UserResponse(
    id=current_user.id,
    username=current_user.username,
    email=current_user.email,
    display_name=current_user.display_name,
    role=current_user.role,
    company_id=current_user.company_id,
    company_name=company.name if company else "",
  )
