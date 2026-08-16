"""公司设置服务"""
from sqlalchemy.orm import Session

from app.models import CompanySettings


def get_or_create_settings(db: Session, company_id: int) -> CompanySettings:
  """获取公司设置，不存在则创建默认值"""
  settings = db.query(CompanySettings).filter(
    CompanySettings.company_id == company_id
  ).first()
  if not settings:
    settings = CompanySettings(company_id=company_id)
    db.add(settings)
    db.commit()
    db.refresh(settings)
  return settings
