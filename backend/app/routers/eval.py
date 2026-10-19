"""评测路由 - 运行评测集并返回报告"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas.agent_eval import AgentEvalReport
from app.schemas.eval import EvalReport
from app.services.agent_eval_runner import run_agent_evaluation
from app.services.eval_runner import run_evaluation
from app.services.settings import get_or_create_settings

router = APIRouter(prefix="/api/eval", tags=["评测"])


@router.post("/run", response_model=EvalReport, summary="运行 RAG 评测")
def run_eval(
  current_user: User = Depends(get_current_user),
  db: Session = Depends(get_db),
):
  """
  对 eval/questions.json 中的 40 道售后回归题执行 RAG 检索，
  返回检索命中率、平均置信度、逐题详情。
  """
  try:
    company_settings = get_or_create_settings(db, current_user.company_id)
    report = run_evaluation(
      current_user.company_id,
      confidence_threshold=company_settings.confidence_threshold,
    )
    return EvalReport(**report)
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
  except Exception as e:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"评测失败: {e}")


@router.post("/agent", response_model=AgentEvalReport, summary="运行 Agent 主循环离线评测")
def run_agent_eval(
  current_user: User = Depends(get_current_user),
):
  """mock 外部 LLM/RAG 边界，真实运行 Agent 主循环、工具与数据库状态。"""
  try:
    return AgentEvalReport(**run_agent_evaluation())
  except ValueError as e:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
  except Exception as e:
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Agent 评测失败: {e}")
