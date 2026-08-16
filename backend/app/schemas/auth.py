"""认证相关 Schema"""
from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
  """注册请求体"""
  username: str = Field(..., min_length=3, max_length=50, description="用户名")
  email: EmailStr = Field(..., description="邮箱")
  password: str = Field(..., min_length=6, description="密码")
  company_name: str = Field(..., min_length=2, max_length=100, description="公司名称")
  display_name: str = Field(default="", max_length=50, description="显示名称")


class LoginRequest(BaseModel):
  """登录请求体"""
  username: str = Field(..., description="用户名")
  password: str = Field(..., description="密码")


class TokenResponse(BaseModel):
  """登录成功响应"""
  access_token: str
  token_type: str = "bearer"


class UserResponse(BaseModel):
  """用户信息响应"""
  id: int
  username: str
  email: str
  display_name: str
  role: str
  company_id: int
  company_name: str

  class Config:
    from_attributes = True
