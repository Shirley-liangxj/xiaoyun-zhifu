import os
import sys
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")


class P0RegressionTests(unittest.TestCase):
  def _db(self):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.database import Base

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()

  def test_unknown_tool_hard_transfers_instead_of_returning_false_success(self):
    """Catches the bug where an unknown tool is logged as pending and the next LLM answer is returned as success."""
    from app.agent import agent_loop
    from app.models import Company
    from app.services.llm import LLMResult

    db = self._db()
    db.add(Company(id=1, name="测试店铺", industry="服饰"))
    db.commit()
    calls = iter([
      LLMResult(
        content="",
        tool_calls=[{
          "id": "call-unknown",
          "type": "function",
          "function": {"name": "unknown_tool", "arguments": "{}"},
        }],
      ),
      LLMResult(content="已经处理完成", tool_calls=[]),
    ])
    original_complete = agent_loop.llm_service.complete
    original_trace = agent_loop.append_trace
    agent_loop.llm_service.complete = lambda *_args, **_kwargs: next(calls)
    agent_loop.append_trace = lambda *_args, **_kwargs: None
    try:
      result = agent_loop.run_agent_turn(db, 1, "帮我处理这个售后问题", customer_name="测试买家")
      self.assertTrue(result["need_human"])
      self.assertTrue(result["human_mode"])
      self.assertEqual(result["intent"], "unknown_tool")
      self.assertNotIn("已经处理完成", result["answer"])
    finally:
      agent_loop.llm_service.complete = original_complete
      agent_loop.append_trace = original_trace
      db.close()

  def test_refund_without_amount_or_days_requires_clarification(self):
    """Catches invented 199 yuan / 5 day defaults when the buyer supplied no refund facts."""
    from app.agent.tools.refund_calc import calc_refund

    result = calc_refund("我要退款")

    self.assertFalse(result["ok"])
    self.assertTrue(result["needs_clarification"])
    self.assertEqual(
      result["result"]["missing_fields"],
      ["order_id", "order_amount", "days_since_purchase"],
    )
    self.assertNotIn("refund_amount", result["result"])

  def test_confirmation_rejects_mismatched_conversation(self):
    """Catches a review action from conversation A changing conversation B."""
    from app.agent.agent_loop import confirm_pending_action
    from app.models import Company, Conversation, HumanReviewAction

    db = self._db()
    db.add(Company(id=1, name="测试店铺", industry="服饰"))
    first = Conversation(company_id=1, customer_name="甲")
    second = Conversation(company_id=1, customer_name="乙")
    db.add_all([first, second])
    db.flush()
    db.add(HumanReviewAction(
      id="review-conversation-bind",
      company_id=1,
      conversation_id=first.id,
      action="refund_review",
      title="退款建议待审核",
      payload='{"refund_amount": 99}',
      status="pending",
    ))
    db.commit()

    with self.assertRaisesRegex(ValueError, "会话不匹配"):
      confirm_pending_action(
        db,
        1,
        "review-conversation-bind",
        conversation_id=second.id,
        customer_name="甲",
      )

    db.refresh(first)
    db.refresh(second)
    action = db.get(HumanReviewAction, "review-conversation-bind")
    self.assertEqual(action.status, "pending")
    self.assertEqual(first.status, "active")
    self.assertEqual(second.status, "active")
    db.close()

  def test_adoption_rate_uses_processed_suggestions_and_tracks_edits(self):
    """Catches pending suggestions being counted in the adoption-rate denominator."""
    from app.services.ai_adoption import summarize_adoption

    summary = summarize_adoption([
      "accepted",
      "edited_and_accepted",
      "rejected",
      "pending",
      "auto_sent",
    ])

    self.assertEqual(summary["processed_suggestions"], 3)
    self.assertEqual(summary["accepted"], 1)
    self.assertEqual(summary["edited_and_accepted"], 1)
    self.assertEqual(summary["rejected"], 1)
    self.assertEqual(summary["pending"], 1)
    self.assertEqual(summary["auto_sent"], 1)
    self.assertEqual(summary["accept_rate"], 66.7)

  def test_buyer_confirmation_enters_waiting_review_with_audit_event(self):
    """Catches buyer confirmation being mislabeled as a completed human review."""
    from app.agent.agent_loop import confirm_pending_action
    from app.models import Company, Conversation, HumanReviewAction, HumanReviewEvent

    db = self._db()
    db.add(Company(id=1, name="测试店铺", industry="服饰"))
    conv = Conversation(company_id=1, customer_name="买家")
    db.add(conv)
    db.flush()
    db.add(HumanReviewAction(
      id="review-buyer-confirm",
      company_id=1,
      conversation_id=conv.id,
      action="refund_review",
      title="退款建议待审核",
      payload='{"order_id":"DEMO-1001","refund_amount":99}',
      status="pending_buyer",
      risk_reason="退款涉及资金动作，必须人工审核",
    ))
    db.commit()

    result = confirm_pending_action(
      db,
      1,
      "review-buyer-confirm",
      conversation_id=conv.id,
      customer_name="买家",
    )

    action = db.get(HumanReviewAction, "review-buyer-confirm")
    events = db.query(HumanReviewEvent).filter_by(action_id=action.id).all()
    self.assertEqual(action.status, "waiting_review")
    self.assertIsNotNone(action.buyer_confirmed_at)
    self.assertEqual(conv.status, "waiting_human")
    self.assertEqual(result["review_status"], "waiting_review")
    self.assertEqual([event.to_status for event in events], ["waiting_review"])
    db.close()

  def test_agent_approval_records_audit_and_returns_result_to_buyer(self):
    """Catches the review flow stopping before an agent decision and buyer-visible result."""
    from app.models import Company, Conversation, HumanReviewAction, HumanReviewEvent, Message, User
    from app.services.human_review import decide_review_action

    db = self._db()
    db.add(Company(id=1, name="测试店铺", industry="服饰"))
    reviewer = User(
      username="reviewer",
      email="reviewer@example.com",
      hashed_password="x",
      display_name="审核坐席",
      company_id=1,
    )
    conv = Conversation(company_id=1, customer_name="买家", status="waiting_human")
    db.add_all([reviewer, conv])
    db.flush()
    action = HumanReviewAction(
      id="review-agent-approve",
      company_id=1,
      conversation_id=conv.id,
      action="refund_review",
      title="退款建议待审核",
      payload='{"order_id":"DEMO-1001","refund_amount":99}',
      status="waiting_review",
      risk_reason="退款涉及资金动作，必须人工审核",
    )
    db.add(action)
    db.commit()

    decided = decide_review_action(
      db,
      company_id=1,
      conversation_id=conv.id,
      review_id=action.id,
      reviewer_id=reviewer.id,
      decision="approved",
      note="资料齐全，同意按试算建议处理",
    )

    db.refresh(conv)
    buyer_message = db.query(Message).filter_by(conversation_id=conv.id, role="agent").one()
    event = db.query(HumanReviewEvent).filter_by(action_id=action.id).one()
    self.assertEqual(decided.status, "approved")
    self.assertEqual(decided.reviewer_id, reviewer.id)
    self.assertIsNotNone(decided.reviewed_at)
    self.assertEqual(decided.review_note, "资料齐全，同意按试算建议处理")
    self.assertEqual(event.from_status, "waiting_review")
    self.assertEqual(event.to_status, "approved")
    self.assertIn("通过审核", buyer_message.content)
    self.assertNotIn("演示", buyer_message.content); self.assertNotIn("本项目", buyer_message.content)
    self.assertEqual(conv.status, "active")

    with self.assertRaisesRegex(ValueError, "已完成审核"):
      decide_review_action(
        db,
        company_id=1,
        conversation_id=conv.id,
        review_id=action.id,
        reviewer_id=reviewer.id,
        decision="rejected",
        note="重复审核",
      )
    db.close()

  def test_review_reject_need_more_info_cross_tenant_and_accept_bypass(self):
    """Covers both remaining review decisions, tenant isolation, and the server-side bypass guard."""
    from fastapi import HTTPException

    from app.models import Company, Conversation, HumanReviewAction, Message, User
    from app.routers.conversations import accept_conversation, decide_conversation_review
    from app.schemas.human_review import HumanReviewDecision

    db = self._db()
    db.add_all([
      Company(id=1, name="甲店", industry="服饰"),
      Company(id=2, name="乙店", industry="服饰"),
    ])
    agent_a = User(
      username="agent-a",
      email="agent-a@example.com",
      hashed_password="x",
      display_name="甲店坐席",
      company_id=1,
    )
    agent_b = User(
      username="agent-b",
      email="agent-b@example.com",
      hashed_password="x",
      display_name="乙店坐席",
      company_id=2,
    )
    conv_reject = Conversation(company_id=1, customer_name="拒绝买家", status="waiting_human")
    conv_more = Conversation(company_id=1, customer_name="补材料买家", status="waiting_human")
    db.add_all([agent_a, agent_b, conv_reject, conv_more])
    db.flush()
    review_reject = HumanReviewAction(
      id="review-reject",
      company_id=1,
      conversation_id=conv_reject.id,
      action="refund_review",
      title="退款建议待审核",
      payload='{"order_id":"DEMO-1002","refund_amount":0}',
      status="waiting_review",
    )
    review_more = HumanReviewAction(
      id="review-more",
      company_id=1,
      conversation_id=conv_more.id,
      action="refund_review",
      title="退款建议待审核",
      payload='{"order_id":"DEMO-1003","refund_amount":88}',
      status="waiting_review",
    )
    db.add_all([review_reject, review_more])
    db.commit()

    with self.assertRaises(HTTPException) as bypass:
      accept_conversation(conv_reject.id, current_user=agent_a, db=db)
    self.assertEqual(bypass.exception.status_code, 409)
    self.assertEqual(conv_reject.status, "waiting_human")

    with self.assertRaises(HTTPException):
      decide_conversation_review(
        conv_reject.id,
        review_reject.id,
        HumanReviewDecision(decision="approved", note="越权尝试"),
        current_user=agent_b,
        db=db,
      )
    db.refresh(review_reject)
    self.assertEqual(review_reject.status, "waiting_review")

    rejected = decide_conversation_review(
      conv_reject.id,
      review_reject.id,
      HumanReviewDecision(decision="rejected", note="不符合退款规则"),
      current_user=agent_a,
      db=db,
    )
    needs_more = decide_conversation_review(
      conv_more.id,
      review_more.id,
      HumanReviewDecision(decision="need_more_info", note="请补充商品照片"),
      current_user=agent_a,
      db=db,
    )
    self.assertEqual(rejected.status, "rejected")
    self.assertEqual(needs_more.status, "need_more_info")
    self.assertEqual(conv_reject.status, "active")
    self.assertEqual(conv_more.status, "waiting_human")
    buyer_results = [row.content for row in db.query(Message).filter(Message.role == "agent").all()]
    self.assertTrue(any("没能" in content or "未通过" in content for content in buyer_results))
    self.assertTrue(any("补充商品照片" in content for content in buyer_results))
    db.close()

  def test_complete_refund_review_journey_reaches_buyer_visible_terminal_result(self):
    """Covers one complete task: tool call -> buyer confirm -> agent approve -> buyer result."""
    from app.agent import agent_loop
    from app.models import Company, HumanReviewAction, HumanReviewEvent, Message, User
    from app.services.human_review import decide_review_action
    from app.services.llm import LLMResult
    from app.services.public_chat import _visible_to_buyer

    db = self._db()
    db.add(Company(id=1, name="测试店铺", industry="服饰"))
    reviewer = User(
      username="journey-reviewer",
      email="journey-reviewer@example.com",
      hashed_password="x",
      display_name="审核坐席",
      company_id=1,
    )
    db.add(reviewer)
    db.commit()

    original_complete = agent_loop.llm_service.complete
    original_trace = agent_loop.append_trace
    agent_loop.llm_service.complete = lambda *_args, **_kwargs: LLMResult(
      content="",
      tool_calls=[{
        "id": "call-refund-journey",
        "type": "function",
        "function": {
          "name": "calc_refund",
          "arguments": '{"order_id":"DEMO-1001","amount":199,"days_since_purchase":5}',
        },
      }],
    )
    agent_loop.append_trace = lambda *_args, **_kwargs: None
    try:
      started = agent_loop.run_agent_turn(
        db,
        1,
        "订单 DEMO-1001，金额 199 元，购买第 5 天，我要申请退款",
        customer_name="闭环买家",
      )
      review_id = started["pending_confirmation"]["id"]
      conversation_id = started["conversation_id"]
      self.assertEqual(started["terminal_state"], "pending_buyer")

      confirmed = agent_loop.confirm_pending_action(
        db,
        1,
        review_id,
        conversation_id=conversation_id,
        customer_name="闭环买家",
      )
      self.assertEqual(confirmed["terminal_state"], "waiting_review")

      decided = decide_review_action(
        db,
        company_id=1,
        conversation_id=conversation_id,
        review_id=review_id,
        reviewer_id=reviewer.id,
        decision="approved",
        note="资料齐全，批准演示退款建议",
      )

      events = db.query(HumanReviewEvent).filter_by(action_id=review_id).order_by(HumanReviewEvent.id).all()
      buyer_messages = db.query(Message).filter_by(conversation_id=conversation_id).all()
      final_message = buyer_messages[-1]
      self.assertEqual(decided.status, "approved")
      self.assertEqual([(e.actor_type, e.to_status) for e in events], [
        ("buyer", "waiting_review"),
        ("agent", "approved"),
      ])
      self.assertEqual(final_message.role, "agent")
      self.assertTrue(_visible_to_buyer(final_message))
      self.assertIn("通过审核", final_message.content)
      self.assertNotIn("演示", final_message.content); self.assertNotIn("本项目", final_message.content)
      self.assertEqual(db.get(HumanReviewAction, review_id).status, "approved")
    finally:
      agent_loop.llm_service.complete = original_complete
      agent_loop.append_trace = original_trace
      db.close()

  def test_accept_suggestion_distinguishes_original_and_edited_content(self):
    """Catches edited suggestions being counted as original acceptance."""
    from app.models import Company, Conversation, Message, User
    from app.routers.conversations import accept_suggestion
    from app.schemas.conversation import AcceptSuggestionRequest

    db = self._db()
    db.add(Company(id=1, name="测试店铺", industry="服饰"))
    user = User(
      username="agent",
      email="agent@example.com",
      hashed_password="x",
      display_name="坐席",
      company_id=1,
    )
    conv = Conversation(company_id=1, customer_name="买家")
    db.add_all([user, conv])
    db.flush()
    original = Message(
      conversation_id=conv.id,
      role="ai_suggestion",
      content="建议原文",
      is_sent=False,
      suggestion_status="pending",
    )
    edited = Message(
      conversation_id=conv.id,
      role="ai_suggestion",
      content="第二条建议原文",
      is_sent=False,
      suggestion_status="pending",
    )
    db.add_all([original, edited])
    db.commit()

    accept_suggestion(
      conv.id,
      original.id,
      AcceptSuggestionRequest(),
      current_user=user,
      db=db,
    )
    accept_suggestion(
      conv.id,
      edited.id,
      AcceptSuggestionRequest(content="坐席编辑后的内容"),
      current_user=user,
      db=db,
    )

    db.refresh(original)
    db.refresh(edited)
    self.assertEqual(original.suggestion_status, "accepted")
    self.assertEqual(edited.suggestion_status, "edited_and_accepted")
    db.close()

  def test_dashboard_returns_adoption_breakdown_and_processed_denominator(self):
    """Catches the dashboard hiding the denominator and suggestion-status breakdown."""
    from app.models import Company, Conversation, Message, User
    from app.routers.stats import get_dashboard_stats

    db = self._db()
    db.add(Company(id=1, name="测试店铺", industry="服饰"))
    user = User(
      username="admin",
      email="admin@example.com",
      hashed_password="x",
      display_name="管理员",
      company_id=1,
    )
    conv = Conversation(company_id=1, customer_name="买家")
    db.add_all([user, conv])
    db.flush()
    for status in ["accepted", "edited_and_accepted", "rejected", "pending", "auto_sent"]:
      db.add(Message(
        conversation_id=conv.id,
        role="ai_suggestion",
        content=status,
        is_sent=status != "pending",
        suggestion_status=status,
      ))
    db.commit()

    report = get_dashboard_stats(current_user=user, db=db)
    overview = report.overview
    self.assertEqual(overview.ai_original_accepted, 1)
    self.assertEqual(overview.ai_edited_accepted, 1)
    self.assertEqual(overview.ai_rejected, 1)
    self.assertEqual(overview.ai_pending, 1)
    self.assertEqual(overview.ai_auto_sent, 1)
    self.assertEqual(overview.ai_processed, 3)
    self.assertEqual(overview.ai_accept_rate, 66.7)
    db.close()

  def test_knowledge_gap_failure_is_persisted_and_retry_reuses_document(self):
    """Covers failure persistence, tenant isolation, document reuse, real FAISS indexing, and retrieval."""
    from tempfile import TemporaryDirectory
    from unittest.mock import patch

    from fastapi import HTTPException

    from app.core.config import settings
    from app.models import Company, KnowledgeDoc, KnowledgeGap, User
    from app.routers.knowledge import resolve_gap
    from app.schemas.knowledge_gap import KnowledgeGapResolve
    from app.services.rag import search_knowledge
    from app.services import vector_store

    db = self._db()
    db.add_all([
      Company(id=1, name="测试店铺", industry="服饰"),
      Company(id=2, name="其他店铺", industry="服饰"),
    ])
    user = User(
      username="knowledge-admin",
      email="knowledge@example.com",
      hashed_password="x",
      display_name="知识管理员",
      company_id=1,
    )
    other_user = User(
      username="other-knowledge-admin",
      email="other-knowledge@example.com",
      hashed_password="x",
      display_name="其他知识管理员",
      company_id=2,
    )
    gap = KnowledgeGap(
      company_id=1,
      question="羽绒服可以机洗吗？",
      status="pending",
      hit_count=1,
    )
    db.add_all([user, other_user, gap])
    db.commit()

    with self.assertRaises(HTTPException) as cross_tenant:
      resolve_gap(
        gap.id,
        KnowledgeGapResolve(suggested_answer="越权答案"),
        current_user=other_user,
        db=db,
      )
    self.assertEqual(cross_tenant.exception.status_code, 404)

    with patch("app.routers.knowledge.index_document", side_effect=RuntimeError("embedding timeout")):
      with self.assertRaises(HTTPException) as failure:
        resolve_gap(
          gap.id,
          KnowledgeGapResolve(suggested_answer="请按洗标清洗。"),
          current_user=user,
          db=db,
        )
    self.assertEqual(failure.exception.status_code, 503)
    db.refresh(gap)
    first_doc_id = gap.knowledge_doc_id
    self.assertEqual(gap.status, "indexing_failed")
    self.assertIn("embedding timeout", gap.last_error)
    self.assertIsNotNone(first_doc_id)
    self.assertEqual(db.query(KnowledgeDoc).count(), 1)

    old_faiss_dir = settings.FAISS_DATA_DIR
    with TemporaryDirectory(dir=BACKEND_DIR) as faiss_dir:
      settings.FAISS_DATA_DIR = faiss_dir
      vector_store._store_cache.clear()
      unit_vector = [1.0] + [0.0] * (settings.EMBEDDING_DIM - 1)
      try:
        with patch("app.services.rag.embedding_service.embed_batch", return_value=[unit_vector]):
          resolved = resolve_gap(
            gap.id,
            KnowledgeGapResolve(suggested_answer="请按洗标清洗。"),
            current_user=user,
            db=db,
          )
        with patch("app.services.rag.embedding_service.embed_text", return_value=unit_vector):
          hits = search_knowledge(1, "羽绒服怎么洗")
        self.assertTrue(any(hit["doc_id"] == first_doc_id for hit in hits))
        self.assertTrue(any("请按洗标清洗" in hit["text"] for hit in hits))
      finally:
        vector_store._store_cache.clear()
        settings.FAISS_DATA_DIR = old_faiss_dir

    db.refresh(gap)
    self.assertEqual(gap.status, "resolved")
    self.assertEqual(gap.knowledge_doc_id, first_doc_id)
    self.assertIsNotNone(gap.resolved_at)
    self.assertEqual(gap.resolution_version, 2)
    self.assertIsNone(gap.last_error)
    self.assertEqual(resolved.knowledge_doc_id, first_doc_id)
    self.assertEqual(db.query(KnowledgeDoc).count(), 1)

    with patch("app.routers.knowledge.index_document") as no_reindex:
      repeated = resolve_gap(
        gap.id,
        KnowledgeGapResolve(suggested_answer="请按洗标清洗。"),
        current_user=user,
        db=db,
      )
    no_reindex.assert_not_called()
    self.assertEqual(repeated.knowledge_doc_id, first_doc_id)
    self.assertEqual(db.query(KnowledgeDoc).count(), 1)
    db.close()

  def test_sqlite_migration_adds_review_and_gap_columns_to_existing_database(self):
    """Catches deployment startup using old SQLite tables without the new P0 fields."""
    from sqlalchemy import create_engine, text

    from app.services.schema_migrate import ensure_sqlite_columns

    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
      conn.execute(text("CREATE TABLE conversations (id INTEGER PRIMARY KEY)"))
      conn.execute(text("CREATE TABLE messages (id INTEGER PRIMARY KEY, role VARCHAR(20), is_sent BOOLEAN)"))
      conn.execute(text("CREATE TABLE human_review_actions (id VARCHAR(64) PRIMARY KEY, status VARCHAR(20))"))
      conn.execute(text("CREATE TABLE knowledge_gaps (id INTEGER PRIMARY KEY, status VARCHAR(20))"))

    ensure_sqlite_columns(engine)

    with engine.connect() as conn:
      review_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(human_review_actions)"))}
      gap_cols = {row[1] for row in conn.execute(text("PRAGMA table_info(knowledge_gaps)"))}
    self.assertTrue({"risk_reason", "buyer_confirmed_at", "reviewer_id", "reviewed_at", "review_note"}.issubset(review_cols))
    self.assertTrue({"knowledge_doc_id", "resolution_version", "last_error", "resolved_at"}.issubset(gap_cols))


if __name__ == "__main__":
  unittest.main()
