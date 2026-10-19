import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class P0AcceptanceTests(unittest.TestCase):
  def test_agent_offline_evaluation_covers_control_layer(self):
    from app.services.agent_eval_runner import run_agent_evaluation

    report = run_agent_evaluation()
    self.assertGreaterEqual(report["total"], 10)
    self.assertEqual(report["execution_mode"], "mock_llm_real_agent_loop")
    self.assertEqual(report["tool_sequence_accuracy"], 100.0)
    self.assertEqual(report["parameter_accuracy"], 100.0)
    self.assertEqual(report["followup_accuracy"], 100.0)
    self.assertEqual(report["terminal_state_accuracy"], 100.0)
    self.assertEqual(report["high_risk_missed_count"], 0)
    self.assertEqual(report["failures"], [])
    self.assertTrue(all("trajectory" in row for row in report["results"]))

  def test_adoption_metrics_exclude_buyer_auto_replies(self):
    from app.services.ai_adoption import summarize_adoption

    summary = summarize_adoption([
      "auto_sent", "auto_sent", "pending", "accepted", "rejected", "legacy_sent"
    ])
    self.assertEqual(summary["human_suggestions"], 3)
    self.assertEqual(summary["accepted"], 1)
    self.assertEqual(summary["rejected"], 1)
    self.assertEqual(summary["pending"], 1)
    self.assertEqual(summary["accept_rate"], 50.0)

  def test_rejected_suggestion_is_not_buyer_visible(self):
    from app.models import Message
    from app.services.public_chat import _visible_to_buyer

    rejected = Message(conversation_id=1, role="ai_suggestion", content="旧建议", is_sent=True, suggestion_status="rejected")
    automatic = Message(conversation_id=1, role="ai_suggestion", content="自动回复", is_sent=True, suggestion_status="auto_sent")
    self.assertFalse(_visible_to_buyer(rejected))
    self.assertTrue(_visible_to_buyer(automatic))

  def test_knowledge_gap_resolves_only_after_index_success(self):
    from app.services.knowledge_gap import resolution_outcome

    self.assertEqual(resolution_outcome(indexed=True), {"status": "resolved", "ok": True})
    self.assertEqual(resolution_outcome(indexed=False), {"status": "pending", "ok": False})

  def test_human_review_is_structured_database_state(self):
    from app.models import HumanReviewAction

    review = HumanReviewAction(
      id="review-test",
      company_id=1,
      conversation_id=1,
      action="refund_review",
      title="退款建议待审核",
      payload='{"refund_amount": 199}',
      status="pending_buyer",
    )
    self.assertEqual(review.status, "pending_buyer")
    self.assertEqual(HumanReviewAction.__tablename__, "human_review_actions")

  def test_refund_flow_persists_and_confirms_review_in_database(self):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.agent import agent_loop
    from app.database import Base
    from app.models import Company, HumanReviewAction
    from app.services.llm import LLMResult

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Company(id=1, name="测试店铺", industry="服饰"))
    db.commit()

    original_complete = agent_loop.llm_service.complete
    original_trace = agent_loop.append_trace
    agent_loop.llm_service.complete = lambda *args, **kwargs: LLMResult(
      content="",
      tool_calls=[{
        "id": "call-refund",
        "type": "function",
        "function": {"name": "calc_refund", "arguments": '{"order_id":"DEMO-1001","amount":199,"days_since_purchase":5}'},
      }],
    )
    agent_loop.append_trace = lambda *_args, **_kwargs: None
    try:
      result = agent_loop.run_agent_turn(db, 1, "订单 DEMO-1001 申请退款", customer_name="测试买家")
      confirmation_id = result["pending_confirmation"]["id"]
      review = db.get(HumanReviewAction, confirmation_id)
      self.assertIsNotNone(review)
      self.assertEqual(review.status, "pending_buyer")

      confirmed = agent_loop.confirm_pending_action(db, 1, confirmation_id, customer_name="测试买家")
      self.assertTrue(confirmed["human_mode"])
      self.assertEqual(db.get(HumanReviewAction, confirmation_id).status, "waiting_review")
    finally:
      agent_loop.llm_service.complete = original_complete
      agent_loop.append_trace = original_trace
      db.close()


if __name__ == "__main__":
  unittest.main()
