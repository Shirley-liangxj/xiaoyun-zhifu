"""用户 Schema"""
from pydantic import BaseModel


class UserOut(BaseModel):
  """用户输出"""
  id: int
  username: str
  email: str
  display_name: str
  role: str
  company_id: int
  is_active: bool

  class Config:
    from_attributes = True
