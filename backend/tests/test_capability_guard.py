import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


class CapabilityGuardTests(unittest.TestCase):
  def _db(self):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

  def test_detects_unsupported_live_data_and_missing_policy_boundaries(self):
    from app.agent import intent_router

    detector = getattr(intent_router, "detect_unsupported_capability", None)
    self.assertIsNotNone(detector, "需要统一的能力边界守卫")

    unsupported = [
      "换货需要把赠品一起退回吗？",
      "这件L码现在还有库存吗？",
      "这款缺货了什么时候能补货？",
      "订单号12345今天能送到吗？",
    ]
    for message in unsupported:
      with self.subTest(message=message):
        self.assertTrue(detector(message))

    supported = [
      "衣服有质量问题怎么退？",
      "下单后多久发货？",
      "快递7天没更新了怎么处理？",
      "这件衣服偏大还是偏小？",
    ]
    for message in supported:
      with self.subTest(message=message):
        self.assertIsNone(detector(message))

  def test_rag_evaluation_uses_capability_guard_before_confidence(self):
    from app.services import eval_runner

    question = {
      "id": 24,
      "category": "安全转人工",
      "question": "这件L码现在还有库存吗？",
      "expected_keywords": [],
      "expected_behavior": "transfer_human",
    }
    high_confidence_sources = [{
      "doc_id": 1,
      "title": "尺码对照表",
      "category": "尺码",
      "text": "L码尺码说明",
      "score": 0.9,
    }]
    with (
      patch.object(eval_runner, "load_questions", return_value=[question]),
      patch.object(eval_runner, "search_knowledge", return_value=high_confidence_sources),
    ):
      report = eval_runner.run_evaluation(1)

    self.assertEqual(report["results"][0]["actual_behavior"], "transfer_human")
    self.assertTrue(report["results"][0]["behavior_correct"])

  def test_agent_guard_transfers_without_calling_the_model(self):
    from app.agent import agent_loop
    from app.models import Company
    from app.services.llm import LLMResult

    db = self._db()
    db.add(Company(id=1, name="测试店铺", industry="服饰"))
    db.commit()
    llm_calls = 0

    def complete(*_args, **_kwargs):
      nonlocal llm_calls
      llm_calls += 1
      return LLMResult(content="错误地回答有库存", tool_calls=[])

    original_complete = agent_loop.llm_service.complete
    original_trace = agent_loop.append_trace
    agent_loop.llm_service.complete = complete
    agent_loop.append_trace = lambda *_args, **_kwargs: None
    try:
      result = agent_loop.run_agent_turn(db, 1, "这件L码现在还有库存吗？")
      self.assertEqual(llm_calls, 0)
      self.assertTrue(result["need_human"])
      self.assertTrue(result["human_mode"])
      self.assertEqual(result["intent"], "transfer")
    finally:
      agent_loop.llm_service.complete = original_complete
      agent_loop.append_trace = original_trace
      db.close()


if __name__ == "__main__":
  unittest.main()
