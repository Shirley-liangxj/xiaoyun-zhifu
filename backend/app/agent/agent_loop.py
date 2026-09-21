"""统一 Agent 入口：function calling 循环 → 工具执行 → 轨迹 → HITL

安全硬约束（代码保证，不依赖提示词）：
1. 注册表无「执行退款」工具，只有 calc_refund 试算。
2. 任一工具返回 needs_human=True → 立即中断循环，按工具分叉（HITL / 转人工），不再追加 LLM。
3. detect_high_risk 在进 LLM 之前拦截，命中则 0 次 LLM。
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.agent.intent_router import INTENT_LABELS, detect_high_risk
from app.agent.tool_registry import list_tool_schemas, run_tool
from app.agent.trajectory import append_trace
from app.models import Conversation, Message
from app.services.ai_suggestion import generate_suggestion
from app.services.errors import ExternalServiceError
from app.services.knowledge_gap import record_knowledge_gap
from app.services.llm import llm_service
from app.services.public_chat import (
  TRANSFER_NOTE,
  _is_human_mode,
  get_or_create_conversation,
)
from app.services.settings import get_or_create_settings

logger = logging.getLogger(__name__)

PENDING_PATH = Path(__file__).resolve().parents[2] / "data" / "pending_confirmations.json"
MAX_TOOL_ROUNDS = 4

AGENT_SYSTEM_PROMPT = """你是服饰电商售后客服助手，只能处理服饰售后相关问题（退换货、尺码、物流、质量、支付、售后政策），可通过工具查询政策、订单与退款试算。

【最高优先级 · 先做这一步判断】用户这句话属于服饰售后范畴吗？
- 不属于（写代码/编程、天气、股票基金、时事政治、翻译、游戏、旅游美食推荐、其他平台业务，以及其他与服饰售后无关的请求）→ 必须调用 transfer_to_human（reason="超出售后范围"）。禁止自己作答，也禁止只用文字说「我帮不了您」来代替调用工具。
- 属于 → 按下面规则调用工具。

工具使用规则：
1. 问政策/规则/怎么退/能不能退/发什么快递/用哪家快递 → 调用 search_policy，再依据返回资料回答；禁止编造政策。
2. 问订单进度、快递到哪了、物流状态 → 调用 query_order；用户未提供单号时向用户追问，禁止编造单号或冒用他人订单。
3. 用户要求退款/退货并涉及金额 → 可先 query_order（有单号时），再 calc_refund 试算；只能试算，禁止承诺已退款/已打款。
4. 投诉、纠纷、情绪激烈 → 调用 transfer_to_human。
5. 仅当问题确实属于服饰售后范畴、且无需查阅资料时（问候、感谢、简单确认、客套话），才可直接简短回答。

回复要求：亲切口语、简洁（一般不超过 150 字），不要暴露内部工具名。"""


def _load_pending() -> dict:
  if not PENDING_PATH.exists():
    return {}
  try:
    with open(PENDING_PATH, encoding="utf-8") as f:
      return json.load(f)
  except Exception:
    return {}


def _save_pending(data: dict) -> None:
  PENDING_PATH.parent.mkdir(parents=True, exist_ok=True)
  with open(PENDING_PATH, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)


def _base_result(
  conv: Conversation,
  ai_msg: Message | None,
  *,
  answer: str,
  confidence: float,
  need_human: bool,
  sources: list,
  intent: dict,
  plan_steps: list,
  pending_confirmation: dict | None,
  human_mode: bool,
) -> dict:
  return {
    "conversation_id": conv.id,
    "message_id": ai_msg.id if ai_msg else 0,
    "answer": answer,
    "confidence": confidence,
    "need_human": need_human,
    "human_mode": human_mode,
    "sources": sources,
    "intent": intent.get("intent"),
    "intent_label": intent.get("label"),
    "plan_steps": plan_steps,
    "pending_confirmation": pending_confirmation,
  }


def _save_ai_message(
  db: Session,
  conv: Conversation,
  content: str,
  confidence: float,
  sources_data: list,
) -> Message:
  ai_msg = Message(
    conversation_id=conv.id,
    role="ai_suggestion",
    content=content.strip(),
    confidence=confidence,
    sources=json.dumps(sources_data, ensure_ascii=False),
    is_sent=True,
  )
  db.add(ai_msg)
  db.commit()
  db.refresh(ai_msg)
  return ai_msg


def _parse_tool_args(raw: str | dict | None) -> dict:
  if raw is None or raw == "":
    return {}
  if isinstance(raw, dict):
    return raw
  try:
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}
  except (json.JSONDecodeError, TypeError):
    return {}


def _tool_call_name(tc: dict) -> str:
  fn = tc.get("function") or {}
  return str(fn.get("name") or tc.get("name") or "").strip()


def _tool_call_id(tc: dict) -> str:
  return str(tc.get("id") or "")


def _tool_call_args(tc: dict) -> dict:
  fn = tc.get("function") or {}
  return _parse_tool_args(fn.get("arguments") if fn else tc.get("arguments"))


def _intent_from_tools(tools_called: list[str], *, high_risk: bool = False, grounded: bool = False) -> dict:
  if high_risk:
    return {
      "intent": "transfer",
      "label": INTENT_LABELS["transfer"],
      "confidence": 1.0,
      "source": "high_risk_regex",
    }
  if not tools_called:
    return {
      "intent": "direct_answer",
      "label": INTENT_LABELS.get("direct_answer", "直接回答"),
      "confidence": 0.7,
      "source": "llm_fc",
      "grounded": grounded,
    }
  key = "+".join(tools_called)
  if "transfer_to_human" in tools_called:
    label = INTENT_LABELS["transfer"]
  elif "calc_refund" in tools_called:
    label = INTENT_LABELS["action"]
  elif "query_order" in tools_called and "search_policy" not in tools_called:
    label = INTENT_LABELS["query"]
  elif "search_policy" in tools_called:
    label = INTENT_LABELS["consult"]
  else:
    label = key
  return {
    "intent": key,
    "label": label,
    "confidence": 0.85,
    "source": "llm_fc",
    "grounded": grounded,
  }


def _do_transfer(
  db: Session,
  conv: Conversation,
  company_settings,
  *,
  confidence: float = 0.35,
  sources_data: list | None = None,
  plan_steps: list | None = None,
  detail: str = "已进入待人工队列",
) -> tuple[Message, str, float, bool, list, list]:
  answer = company_settings.reject_message or TRANSFER_NOTE
  conv.status = "waiting_human"
  need_human = True
  sources_data = sources_data or []
  ai_msg = _save_ai_message(db, conv, answer, confidence, sources_data)
  steps = list(plan_steps or [])
  steps.append({
    "id": "transfer",
    "title": "转人工",
    "status": "needs_confirm",
    "detail": detail,
    "demo": False,
  })
  return ai_msg, answer, confidence, need_human, sources_data, steps


def _build_refund_pending(
  company_id: int,
  conv: Conversation,
  customer_name: str,
  refund_out: dict,
) -> tuple[dict, str]:
  result = refund_out.get("result") or {}
  confirmation_id = str(uuid.uuid4())
  pending = {
    "id": confirmation_id,
    "action": "refund_execute",
    "title": "退款执行待确认",
    "detail": refund_out.get("summary", ""),
    "payload": result,
    "demo": True,
  }
  store = _load_pending()
  store[confirmation_id] = {
    "company_id": company_id,
    "conversation_id": conv.id,
    "customer_name": customer_name,
    "payload": result,
    "status": "pending",
  }
  _save_pending(store)
  answer = (
    f"{refund_out.get('summary', '')}\n\n"
    "请点击下方「确认提交给人工」后，坐席将按演示流程处理；"
    "系统不会自动打款。"
  )
  return pending, answer


def run_agent_turn(
  db: Session,
  company_id: int,
  message: str,
  conversation_id: int | None = None,
  customer_name: str = "访客",
) -> dict:
  company_settings = get_or_create_settings(db, company_id)
  threshold = company_settings.confidence_threshold
  conv = get_or_create_conversation(db, company_id, conversation_id, customer_name)

  db.add(Message(conversation_id=conv.id, role="customer", content=message, is_sent=True))
  db.commit()

  # ① 已在人工队列：保持旧行为
  if conv.status == "waiting_human":
    try:
      generate_suggestion(db, conv, message)
    except Exception:
      pass
    intent = {
      "intent": "transfer",
      "label": INTENT_LABELS["transfer"],
      "confidence": 1.0,
      "source": "human_mode",
    }
    append_trace({
      "conversation_id": conv.id,
      "company_id": company_id,
      "input": message,
      "intent": intent,
      "tools": [],
      "output": "",
      "needs_human": True,
      "grounded": False,
    })
    return _base_result(
      conv, None,
      answer="",
      confidence=0.0,
      need_human=True,
      sources=[],
      intent=intent,
      plan_steps=[],
      pending_confirmation=None,
      human_mode=True,
    )

  # ② 高危正则前置拦截：0 次 LLM
  if detect_high_risk(message):
    plan_steps = [{
      "id": "high_risk",
      "title": "高危前置拦截",
      "status": "done",
      "detail": "正则命中投诉/法律/曝光类，未调用大模型",
      "demo": False,
    }]
    ai_msg, answer, confidence, need_human, sources_data, plan_steps = _do_transfer(
      db, conv, company_settings,
      confidence=0.35,
      plan_steps=plan_steps,
      detail="高危关键词前置拦截，已进入待人工队列",
    )
    intent = _intent_from_tools([], high_risk=True)
    db.commit()
    append_trace({
      "conversation_id": conv.id,
      "company_id": company_id,
      "input": message,
      "intent": intent,
      "tools": [],
      "output": answer,
      "needs_human": True,
      "grounded": False,
      "source": "high_risk_regex",
      "llm_calls": 0,
    })
    return _base_result(
      conv, ai_msg,
      answer=answer,
      confidence=confidence,
      need_human=need_human,
      sources=sources_data,
      intent=intent,
      plan_steps=plan_steps,
      pending_confirmation=None,
      human_mode=_is_human_mode(db, conv),
    )

  # ③ function calling 主循环
  tools_schema = list_tool_schemas()
  messages: list[dict] = [
    {"role": "system", "content": AGENT_SYSTEM_PROMPT},
    {"role": "user", "content": message},
  ]
  tools_log: list[dict] = []
  tools_called: list[str] = []
  plan_steps: list[dict] = []
  sources_data: list = []
  pending = None
  grounded = False
  confidence = 0.7
  need_human = False
  answer = ""
  ai_msg = None
  llm_calls = 0
  interrupted = False
  interrupt_reason = None

  try:
    for _round in range(MAX_TOOL_ROUNDS):
      result = llm_service.complete(
        messages,
        temperature=0,
        tools=tools_schema,
      )
      llm_calls += 1
      tool_calls = result.tool_calls or []

      if not tool_calls:
        answer = (result.content or "").strip()
        # 仅当整轮从未调过任何工具时标注「未检索」；有工具后再生成终答不算 direct
        if not tools_called and not grounded:
          plan_steps.append({
            "id": "direct",
            "title": "直接回答",
            "status": "done",
            "detail": "未检索知识库（模型未调用 search_policy）",
            "demo": False,
          })
        break

      # 把 assistant 的 tool_calls 回灌进 messages（GLM OpenAI 兼容）
      assistant_msg: dict = {
        "role": "assistant",
        "content": result.content or None,
        "tool_calls": tool_calls,
      }
      messages.append(assistant_msg)

      for tc in tool_calls:
        name = _tool_call_name(tc)
        args = _tool_call_args(tc)
        call_id = _tool_call_id(tc)

        # 原始用户 message 与模型参数分开传；calc_refund 穿着检测必须跑在用户原话上
        out = run_tool(
          name,
          message,
          company_id=company_id,
          fallback_to_first=False,
          **args,
        )
        tools_log.append({"name": name, "args": args, "output": out})
        tools_called.append(name)

        demo = (out.get("source") or "").startswith("demo") or bool(
          (out.get("result") or {}).get("demo")
        )
        plan_steps.append({
          "id": name,
          "title": name,
          "status": "done" if out.get("ok") else "pending",
          "detail": out.get("summary", ""),
          "demo": demo,
        })

        # —— search_policy：知识缺口回流 + 低置信硬中断 ——
        if name == "search_policy":
          res = out.get("result") or {}
          srcs = res.get("sources") or []
          conf = float(res.get("confidence") or 0.0)
          confidence = conf
          grounded = True
          sources_data = [
            {
              "doc_id": s.get("doc_id", 0),
              "title": s.get("title", ""),
              "category": s.get("category", ""),
              "text": s.get("text", ""),
              "score": s.get("score", 0.0),
            }
            for s in srcs
          ]
          record_knowledge_gap(db, company_id, message, conf, threshold)

          if conf < threshold or not srcs:
            # 低置信/无资料：忽略模型后续意图，立即转人工，不再追加 LLM
            messages.append({
              "role": "tool",
              "tool_call_id": call_id,
              "content": json.dumps(out, ensure_ascii=False),
            })
            ai_msg, answer, confidence, need_human, sources_data, plan_steps = _do_transfer(
              db, conv, company_settings,
              confidence=conf if conf > 0 else 0.25,
              sources_data=sources_data,
              plan_steps=plan_steps,
              detail=f"检索置信度 {conf:.2f} < 阈值 {threshold}，已转人工",
            )
            interrupted = True
            interrupt_reason = "low_confidence_rag"
            break

        # —— needs_human 一票否决（代码判定）——
        if out.get("needs_human"):
          messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps(out, ensure_ascii=False),
          })
          if name == "calc_refund":
            # HITL 确认卡：不立刻改 waiting_human
            pending, answer = _build_refund_pending(
              company_id, conv, customer_name, out
            )
            confidence = 0.75
            need_human = True
            ai_msg = _save_ai_message(db, conv, answer, confidence, sources_data)
            plan_steps.append({
              "id": "hitl",
              "title": "待人工确认执行",
              "status": "needs_confirm",
              "detail": "高风险动作，需买家确认后进入坐席队列",
              "demo": False,
            })
            interrupted = True
            interrupt_reason = "calc_refund_hitl"
          else:
            # transfer_to_human 或其他 needs_human：立刻转人工
            ai_msg, answer, confidence, need_human, sources_data, plan_steps = _do_transfer(
              db, conv, company_settings,
              confidence=0.35,
              sources_data=sources_data,
              plan_steps=plan_steps,
              detail=(out.get("result") or {}).get("reason") or out.get("summary") or "已转人工",
            )
            interrupted = True
            interrupt_reason = name or "needs_human"
          break

        messages.append({
          "role": "tool",
          "tool_call_id": call_id,
          "content": json.dumps(out, ensure_ascii=False),
        })

      if interrupted:
        break
    else:
      # for-else：正常跑完 MAX_TOOL_ROUNDS 仍未得到最终回答
      if not answer and not interrupted:
        ai_msg, answer, confidence, need_human, sources_data, plan_steps = _do_transfer(
          db, conv, company_settings,
          confidence=0.3,
          sources_data=sources_data,
          plan_steps=plan_steps,
          detail=f"超过最大工具轮数 {MAX_TOOL_ROUNDS}，兜底转人工",
        )
        interrupted = True
        interrupt_reason = "max_rounds"

  except (ValueError, ExternalServiceError) as e:
    logger.warning("agent FC loop failed: %s", e)
    ai_msg, answer, confidence, need_human, sources_data, plan_steps = _do_transfer(
      db, conv, company_settings,
      confidence=0.2,
      sources_data=sources_data,
      plan_steps=plan_steps,
      detail=f"大模型调用失败，已转人工：{e}",
    )
    interrupt_reason = "llm_error"

  # 正常结束：模型给出最终文本（未走中断路径）
  if ai_msg is None:
    if not answer:
      answer = company_settings.reject_message or TRANSFER_NOTE
      need_human = True
      conv.status = "waiting_human"
      confidence = 0.3
    ai_msg = _save_ai_message(db, conv, answer, confidence, sources_data)

  intent = _intent_from_tools(tools_called, grounded=grounded)
  if interrupt_reason:
    intent["interrupt"] = interrupt_reason

  db.commit()
  append_trace({
    "conversation_id": conv.id,
    "company_id": company_id,
    "input": message,
    "intent": intent,
    "tools": [
      {
        "name": t["name"],
        "args": t.get("args"),
        "summary": (t.get("output") or {}).get("summary"),
        "source": (t.get("output") or {}).get("source"),
        "needs_human": (t.get("output") or {}).get("needs_human"),
      }
      for t in tools_log
    ],
    "output": answer,
    "needs_human": need_human,
    "pending_confirmation_id": pending["id"] if pending else None,
    "grounded": grounded,
    "llm_calls": llm_calls,
    "interrupt_reason": interrupt_reason,
  })

  return _base_result(
    conv,
    ai_msg,
    answer=answer,
    confidence=confidence,
    need_human=need_human,
    sources=sources_data,
    intent=intent,
    plan_steps=plan_steps,
    pending_confirmation=pending,
    human_mode=_is_human_mode(db, conv),
  )


def confirm_pending_action(
  db: Session,
  company_id: int,
  confirmation_id: str,
  conversation_id: int | None = None,
  customer_name: str = "访客",
) -> dict:
  store = _load_pending()
  item = store.get(confirmation_id)
  if not item or item.get("company_id") != company_id:
    raise ValueError("确认单不存在或已失效")
  if item.get("status") != "pending":
    raise ValueError("该确认单已处理")

  conv = get_or_create_conversation(
    db, company_id, conversation_id or item.get("conversation_id"), customer_name
  )
  payload = item.get("payload") or {}
  item["status"] = "confirmed"
  store[confirmation_id] = item
  _save_pending(store)

  conv.status = "waiting_human"
  answer = (
    f"【演示】已收到您的确认：建议退款 ¥{payload.get('refund_amount', 0)} "
    f"（订单 {payload.get('order_id', 'DEMO')}）。"
    "已转入人工队列，坐席将继续处理。系统未自动打款。"
  )
  ai_msg = _save_ai_message(db, conv, answer, 0.9, [])
  append_trace({
    "conversation_id": conv.id,
    "company_id": company_id,
    "input": f"[confirm] {confirmation_id}",
    "intent": {"intent": "action", "label": "操作类", "source": "hitl_confirm"},
    "tools": [],
    "output": answer,
    "needs_human": True,
    "pending_confirmation_id": confirmation_id,
    "confirmed": True,
    "grounded": False,
  })
  return {
    "conversation_id": conv.id,
    "message_id": ai_msg.id,
    "answer": answer,
    "confidence": 0.9,
    "need_human": True,
    "human_mode": True,
    "sources": [],
    "intent": "action",
    "intent_label": "操作类",
    "plan_steps": [
      {"id": "hitl", "title": "人工确认", "status": "done", "detail": "买家已确认，已进待人工", "demo": True}
    ],
    "pending_confirmation": None,
  }
