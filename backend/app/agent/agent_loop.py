"""统一 Agent 入口：function calling 循环 → 工具执行 → 轨迹 → HITL

安全硬约束（代码保证，不依赖提示词）：
1. 注册表无「执行退款」工具，只有 calc_refund 试算。
2. 任一工具返回 needs_human=True → 立即中断循环，按工具分叉（HITL / 转人工），不再追加 LLM。
3. detect_high_risk 在进 LLM 之前拦截，命中则 0 次 LLM。
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from app.agent.intent_router import INTENT_LABELS, detect_high_risk, detect_unsupported_capability
from app.agent.tools.order_query import extract_order_id
from app.agent.tool_registry import list_tool_schemas, run_tool
from app.agent.trajectory import append_trace
from app.models import Conversation, HumanReviewAction, Message
from app.services.ai_suggestion import generate_suggestion
from app.services.errors import ExternalServiceError
from app.services.knowledge_gap import record_knowledge_gap
from app.services.human_review import add_review_event
from app.services.llm import llm_service
from app.services.public_chat import (
  TRANSFER_NOTE,
  _is_human_mode,
  get_or_create_conversation,
)
from app.services.settings import get_or_create_settings

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 4

AGENT_SYSTEM_PROMPT = """你是服饰电商售后客服助手，只能处理服饰售后相关问题（退换货、尺码、物流、质量、支付、售后政策），可通过工具查询政策、订单与退款试算。

【第一优先 · 先看懂这是一通连续对话】
你现在看到的是一通多轮对话，不是孤立的一句话。必须先结合上文判断用户这句话在做什么：
- 如果上一轮你在向用户索取信息（订单号、金额、购买天数、是否穿过等），用户这一条是补充答案 → 直接把补充的信息填进去，继续完成上一轮那件事，禁止把它当成一个全新问题重新开始。
- 典型：上一轮你问「请提供订单号」，用户回「DEMO-1002」→ 这代表继续上一轮的退货/查询任务，不是单纯查物流。
- 只有用户明确换了话题，才重新判断意图。

【第二优先 · 是否属于服饰售后范畴】
- 不属于（写代码/编程、天气、股票基金、时事政治、翻译、游戏、旅游美食推荐、其他平台业务，以及其他与服饰售后无关的请求）→ 必须调用 transfer_to_human（reason="超出售后范围"）。禁止自己作答，也禁止只用文字说「我帮不了您」来代替调用工具。
- 属于 → 按下面规则调用工具。

工具使用规则：
1. 【先分清「问规则」还是「要办事」——这一步做错，后面全错】
   - 只是**询问**政策/规则/流程/费用/时效/条件（句子里常带「吗」「怎么」「能不能」「多久」「多少」「需要…吗」「谁承担」）→ 一律调用 search_policy，查资料后回答。
     例：「退货需要自己付运费吗」「退货运费谁承担」「退款多久到账」「能换货吗」「七天无理由怎么算」→ 全部走 search_policy。
     这类问题**禁止**直接进退款流程，**禁止**反问「您要退哪件商品」。
   - 用户**明确表示现在就要办理**退货/退款（如「我要退货」「帮我退掉」「申请退款」「这件不要了退了吧」+ 单号）→ 才走第 3 条。
2. 问订单进度、快递到哪了、物流状态 → 调用 query_order；用户未提供单号时向用户追问，禁止编造单号或冒用他人订单。
3. 用户要求退款/退货（动作意图）：
   - 没有单号 → 先向用户要单号（一句话问完，不要一次问多个问题）。
   - 拿到单号 → 调用 query_order 取订单信息，再调用 calc_refund 试算。订单结果里已有金额（amount）和购买天数（days_since_purchase），直接用作 calc_refund 的入参，禁止再让用户重复报金额、天数。
   - 订单里只有一个商品时，直接按这个商品试算，禁止反问「要退哪件商品」。
   - 订单里也判断不了的（比如是否已穿着），可以追问一次；用户回答后直接试算。
   - 只能试算，禁止承诺已退款/已打款。
4. 投诉、纠纷、情绪激烈 → 调用 transfer_to_human。
5. 仅当问题确实属于服饰售后范畴、且无需查阅资料时（问候、感谢、简单确认、客套话），才可直接简短回答。

回复要求：亲切口语、简洁（一般不超过 150 字），不要暴露内部工具名、规则编号、「试算」「演示数据」等内部措辞，不要重复用户已经说过的信息。

【禁止空转】不允许把「请稍等」「我马上为您查询」「我先帮您查一下」这类话当作最终回复发给用户 —— 那等于把用户晾在原地。要查信息就**当场调用工具**（同一轮里直接 call query_order / calc_refund / search_policy），查完再回答；确实查不了就直接给结论或说明原因。"""

HISTORY_LIMIT = 12

# 模型常见的「空转」话术：说要查，但压根没调工具，把用户晾在原地
VACUOUS_RE = re.compile(r"请稍等|稍候|稍等一下|马上|这就|我帮您查|帮您查询|为您查询|正在查询|正在为您")


def _looks_vacuous(text: str) -> bool:
  """判断这句回复是不是「只说去查、其实没查」的空转话术。"""
  t = (text or "").strip()
  return bool(t) and len(t) <= 80 and bool(VACUOUS_RE.search(t))


def _load_history(db: Session, conversation_id: int, limit: int = HISTORY_LIMIT) -> list[Message]:
  """取当前会话最近若干条可见消息，作为模型的多轮上下文。"""
  rows = (
    db.query(Message)
    .filter(Message.conversation_id == conversation_id, Message.is_internal.is_(False))
    .order_by(Message.id.desc())
    .limit(limit)
    .all()
  )
  rows.reverse()
  return rows


def _history_to_llm(rows: list[Message]) -> list[dict]:
  """把历史消息转成 OpenAI 兼容的对话格式。"""
  out: list[dict] = []
  for m in rows:
    content = (m.content or "").strip()
    if not content:
      continue
    if m.role == "customer":
      out.append({"role": "user", "content": content})
    elif m.role == "agent":
      out.append({"role": "assistant", "content": f"（人工客服）{content}"})
    elif m.role == "ai_suggestion" and m.is_sent:
      out.append({"role": "assistant", "content": content})
  return out


def _carry_over_hint(rows: list[Message], message: str) -> str:
  """短回复承接上一轮追问：避免「用户只回了个单号」被当成新意图。"""
  text = (message or "").strip()
  last_ai = ""
  for m in reversed(rows):
    if m.role in ("ai_suggestion", "agent") and (m.content or "").strip():
      last_ai = m.content.strip()
      break
  if not last_ai:
    return ""

  order_id = extract_order_id(text)
  compact = len(text) <= 24
  asked_for_order = ("订单号" in last_ai) or ("单号" in last_ai)

  recent_user_text = " ".join(
    (m.content or "") for m in rows[-6:] if m.role == "customer"
  )
  wants_refund = any(
    w in recent_user_text or w in text for w in ("退款", "退货", "退钱", "退掉", "申请退")
  )

  if order_id and compact and asked_for_order and wants_refund:
    return (
      f"\n\n（对话上下文提示：用户此前明确要求退款/退货，这一句只是在补充订单号 {order_id}。"
      "请不要反问「退哪件商品」「多少钱」「买了几天」——直接调用 query_order 查询该订单，"
      "用订单返回的金额与购买天数立即调用 calc_refund 试算退款金额。）"
    )
  if order_id and compact and asked_for_order:
    return (
      f"\n\n（对话上下文提示：上一轮客服正在向用户索取订单号，用户这条只是在补充订单号 {order_id}。"
      "请承接上一轮的任务继续处理，不要当成新的查询问题。）"
    )
  if len(text) <= 12 and last_ai.rstrip().endswith(("？", "?")):
    return (
      "\n\n（对话上下文提示：上一轮客服在向用户追问，用户这条是在回答追问。"
      "请承接上一轮任务继续处理，不要重新判断意图。）"
    )
  return ""


def _clear_pending_meta(db: Session, conversation_id: int, confirmation_id: str) -> None:
  """确认单已处理：清掉该消息上的待确认按钮，避免重复点击。"""
  rows = (
    db.query(Message)
    .filter(Message.conversation_id == conversation_id, Message.meta.isnot(None))
    .all()
  )
  for m in rows:
    meta = parse_meta_safe(m.meta)
    pc = meta.get("pending_confirmation")
    if isinstance(pc, dict) and pc.get("id") == confirmation_id:
      meta["pending_confirmation"] = None
      m.meta = json.dumps(meta, ensure_ascii=False)
  db.commit()


def parse_meta_safe(raw):
  if not raw:
    return {}
  try:
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}
  except Exception:
    return {}


def _last_order_id(tools_log: list[dict]) -> str | None:
  """从本轮工具结果里取查询到的订单号，用于试算补参。"""
  for t in reversed(tools_log):
    if t.get("name") != "query_order":
      continue
    oid = ((t.get("output") or {}).get("result") or {}).get("order_id")
    if oid:
      return str(oid)
  return None


def _order_card(tools_log: list[dict]) -> dict | None:
  """把订单查询结果转成买家端可渲染的结构化卡片。"""
  for t in tools_log:
    if t.get("name") != "query_order":
      continue
    r = (t.get("output") or {}).get("result") or {}
    if not r.get("order_id"):
      continue
    return {
      "type": "order",
      "order_id": r.get("order_id"),
      "product": r.get("product"),
      "status": r.get("status"),
      "express": r.get("express"),
      "tracking_no": r.get("tracking_no"),
      "logistics": r.get("logistics"),
      "amount": r.get("amount"),
      "demo": bool(r.get("demo")),
    }
  return None


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
  card: dict | None = None,
) -> dict:
  if pending_confirmation:
    terminal_state = "pending_buyer"
  elif intent.get("interrupt") == "needs_clarification":
    terminal_state = "needs_clarification"
  elif conv.status == "waiting_human":
    terminal_state = "waiting_human"
  else:
    terminal_state = "answered"
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
    "terminal_state": terminal_state,
    "card": card,
  }


def _save_ai_message(
  db: Session,
  conv: Conversation,
  content: str,
  confidence: float,
  sources_data: list,
  meta: dict | None = None,
) -> Message:
  ai_msg = Message(
    conversation_id=conv.id,
    role="ai_suggestion",
    content=content.strip(),
    confidence=confidence,
    sources=json.dumps(sources_data, ensure_ascii=False),
    is_sent=True,
    suggestion_status="auto_sent",
    meta=json.dumps(meta, ensure_ascii=False) if meta else None,
  )
  db.add(ai_msg)
  db.commit()
  db.refresh(ai_msg)
  return ai_msg


def _attach_meta(
  db: Session,
  ai_msg: Message | None,
  *,
  intent_label: str | None,
  plan_steps: list,
  pending_confirmation: dict | None,
  card: dict | None,
  internal_note: str | None = None,
) -> None:
  """把执行计划/待确认动作/业务卡片落到消息上，刷新或轮询后不会丢失。

  meta 里的 plan_steps / intent_label / internal_note 属于「坐席可见」内容，
  买家端接口会做白名单过滤，绝不下发。
  """
  if ai_msg is None:
    return
  meta = parse_meta_safe(getattr(ai_msg, "meta", None))
  meta.update({
    "intent_label": intent_label,
    "plan_steps": plan_steps or [],
    "pending_confirmation": pending_confirmation,
    "card": card,
  })
  if internal_note:
    meta["internal_note"] = internal_note
  ai_msg.meta = json.dumps(meta, ensure_ascii=False)
  db.commit()


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
  ai_msg = _save_ai_message(
    db, conv, answer, confidence, sources_data,
    meta={"internal_note": detail},
  )
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
  db: Session,
  company_id: int,
  conv: Conversation,
  customer_name: str,
  refund_out: dict,
) -> tuple[dict, str, str]:
  """生成 HITL 待确认动作。

  返回 (pending, buyer_answer, internal_note)：
  - buyer_answer 是买家看到的客服话术（不含规则/试算/演示等内部措辞）
  - internal_note 只给坐席看（试算明细 + 风险说明）
  """
  result = refund_out.get("result") or {}
  confirmation_id = str(uuid.uuid4())
  internal_note = refund_out.get("summary", "")
  pending = {
    "id": confirmation_id,
    "action": "refund_review",
    "title": "退款建议待审核",
    "detail": internal_note,
    "payload": result,
    "demo": True,
  }
  db.add(HumanReviewAction(
    id=confirmation_id,
    company_id=company_id,
    conversation_id=conv.id,
    customer_name=customer_name,
    action="refund_review",
    title="退款建议待审核",
    detail=internal_note,
    payload=json.dumps(result, ensure_ascii=False),
    status="pending_buyer",
    risk_reason="退款涉及资金动作，必须由坐席审核；系统仅提供试算。",
  ))
  db.commit()
  answer = refund_out.get("buyer_text") or (
    "已经帮您核对好了，需要我帮您提交退货申请吗？"
  )
  return pending, answer, internal_note


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

  # 先取历史（不含本条），作为多轮上下文
  history = _load_history(db, conv.id)

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
    _attach_meta(
      db, ai_msg,
      intent_label=intent.get("label"),
      plan_steps=plan_steps,
      pending_confirmation=None,
      card=None,
    )
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

  # ③ 能力边界守卫：相似资料置信度再高，也不能猜实时库存、订单或缺失政策
  capability_reason = detect_unsupported_capability(message)
  if capability_reason:
    plan_steps = [{
      "id": "capability_guard",
      "title": "能力边界判断",
      "status": "done",
      "detail": capability_reason,
      "demo": False,
    }]
    ai_msg, answer, confidence, need_human, sources_data, plan_steps = _do_transfer(
      db, conv, company_settings,
      confidence=0.35,
      plan_steps=plan_steps,
      detail="超出当前可核验的数据边界，已进入待人工队列",
    )
    intent = {
      "intent": "transfer",
      "label": INTENT_LABELS["transfer"],
      "confidence": 1.0,
      "source": "capability_guard",
    }
    _attach_meta(
      db, ai_msg,
      intent_label=intent.get("label"),
      plan_steps=plan_steps,
      pending_confirmation=None,
      card=None,
    )
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
      "source": "capability_guard",
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

  # ④ function calling 主循环（带多轮上下文）
  tools_schema = list_tool_schemas()
  messages: list[dict] = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
  messages.extend(_history_to_llm(history))
  messages.append({"role": "user", "content": message + _carry_over_hint(history, message)})
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

        # 参数补全重试：模型没把单号传给试算时，用本轮查到的订单号补齐再算一次
        if name == "calc_refund" and out.get("needs_clarification"):
          oid = str(args.get("order_id") or "").strip() or extract_order_id(message) or _last_order_id(tools_log)
          if oid:
            retry = run_tool(
              "calc_refund", message,
              company_id=company_id,
              fallback_to_first=False,
              order_id=oid,
              amount=args.get("amount"),
              days_since_purchase=args.get("days_since_purchase"),
            )
            if retry.get("ok"):
              out = retry
              tools_log[-1]["output"] = retry

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

        # 缺少业务关键参数时直接追问，不允许工具自行补造演示参数。
        if out.get("needs_clarification"):
          answer = out.get("buyer_text") or out.get("summary") or "请补充必要信息后再试。"
          confidence = 1.0
          plan_steps[-1]["status"] = "needs_input"
          plan_steps[-1]["detail"] = out.get("summary") or answer
          interrupted = True
          interrupt_reason = "needs_clarification"
          break

        # 未知工具、参数校验失败或工具异常不能继续生成“已完成”。
        if not out.get("ok") and (out.get("source") == "system" or out.get("error_code")):
          ai_msg, answer, confidence, need_human, sources_data, plan_steps = _do_transfer(
            db, conv, company_settings,
            confidence=0.2,
            sources_data=sources_data,
            plan_steps=plan_steps,
            detail=out.get("summary") or "工具调用失败，已转人工",
          )
          interrupted = True
          interrupt_reason = name or "tool_error"
          break

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
          eligible = bool((out.get("result") or {}).get("eligible"))
          if name == "calc_refund" and eligible:
            # HITL 确认卡：不立刻改 waiting_human
            pending, answer, internal_note = _build_refund_pending(
              db, company_id, conv, customer_name, out
            )
            confidence = 0.75
            need_human = True
            ai_msg = _save_ai_message(
              db, conv, answer, confidence, sources_data,
              meta={"internal_note": internal_note},
            )
            plan_steps.append({
              "id": "hitl",
              "title": "提交人工审核",
              "status": "needs_confirm",
              "detail": "高风险退款建议，需买家确认后提交坐席审核；系统不会自动退款",
              "demo": False,
            })
            interrupted = True
            interrupt_reason = "calc_refund_hitl"
          else:
            # transfer_to_human，或不符合自助退款条件（超期/已穿着）：直接转人工，
            # 不给买家「确认提交」按钮，避免让买家确认一个注定被拒的动作
            ai_msg, answer, confidence, need_human, sources_data, plan_steps = _do_transfer(
              db, conv, company_settings,
              confidence=0.35,
              sources_data=sources_data,
              plan_steps=plan_steps,
              detail=(out.get("result") or {}).get("reason") or out.get("summary") or "已转人工",
            )
            if name == "calc_refund" and out.get("buyer_text"):
              ai_msg.content = out["buyer_text"].strip()
              answer = ai_msg.content
              db.commit()
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

  # 空转兜底：模型只回了「请稍等 / 我帮您查」却没真正调工具 —— 代码替它把事办完。
  # 这是「模型优先 + 代码兜底」的双保险：核心退款链路不允许因为模型偷懒而断在半路。
  if ai_msg is None and not interrupted and not tools_called and _looks_vacuous(answer):
    forced_oid = extract_order_id(message)
    if forced_oid:
      q_out = run_tool(
        "query_order", message, company_id=company_id,
        fallback_to_first=False, order_id=forced_oid,
      )
      tools_log.append({"name": "query_order", "args": {"order_id": forced_oid}, "output": q_out})
      r_out = run_tool(
        "calc_refund", message, company_id=company_id,
        fallback_to_first=False, order_id=forced_oid,
      )
      tools_log.append({"name": "calc_refund", "args": {"order_id": forced_oid}, "output": r_out})
      tools_called = ["query_order", "calc_refund"]
      grounded = True
      for t in tools_log:
        plan_steps.append({
          "id": t["name"],
          "title": t["name"],
          "status": "done" if (t["output"] or {}).get("ok") else "pending",
          "detail": (t["output"] or {}).get("summary", ""),
          "demo": True,
        })
      if (r_out.get("result") or {}).get("eligible"):
        pending, answer, internal_note = _build_refund_pending(
          db, company_id, conv, customer_name, r_out
        )
        confidence = 0.75
        need_human = True
        ai_msg = _save_ai_message(
          db, conv, answer, confidence, [],
          meta={"internal_note": internal_note},
        )
        plan_steps.append({
          "id": "hitl",
          "title": "提交人工审核",
          "status": "needs_confirm",
          "detail": "高风险退款建议，需买家确认后提交坐席审核；系统不会自动退款",
          "demo": False,
        })
      else:
        ai_msg, answer, confidence, need_human, sources_data, plan_steps = _do_transfer(
          db, conv, company_settings,
          confidence=0.35,
          sources_data=sources_data,
          plan_steps=plan_steps,
          detail=(r_out.get("result") or {}).get("reason") or "退款条件不满足，转人工",
        )
        if r_out.get("buyer_text"):
          ai_msg.content = r_out["buyer_text"].strip()
          answer = ai_msg.content
          db.commit()
      interrupt_reason = "vacuous_fallback"

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

  card = _order_card(tools_log)
  _attach_meta(
    db, ai_msg,
    intent_label=intent.get("label"),
    plan_steps=plan_steps,
    pending_confirmation=pending,
    card=card,
  )

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
    card=card,
  )


def confirm_pending_action(
  db: Session,
  company_id: int,
  confirmation_id: str,
  conversation_id: int | None = None,
  customer_name: str = "访客",
) -> dict:
  item = db.query(HumanReviewAction).filter(
    HumanReviewAction.id == confirmation_id,
    HumanReviewAction.company_id == company_id,
  ).first()
  if not item:
    raise ValueError("确认单不存在或已失效")
  if item.status not in {"pending", "pending_buyer"}:
    raise ValueError("该确认单已处理")

  if conversation_id is not None and conversation_id != item.conversation_id:
    raise ValueError("确认单与会话不匹配")

  conv = get_or_create_conversation(
    db, company_id, item.conversation_id, customer_name
  )
  try:
    payload = json.loads(item.payload or "{}")
  except json.JSONDecodeError:
    payload = {}
  from_status = item.status
  item.status = "waiting_review"
  item.buyer_confirmed_at = datetime.utcnow()
  add_review_event(
    db,
    item,
    from_status=from_status,
    to_status="waiting_review",
    actor_type="buyer",
    note="买家确认提交人工审核",
  )
  db.commit()

  conv.status = "waiting_human"
  # 买家看到的是客服话术；金额/单号等内部明细只写 internal_note
  answer = (
    "好的，退货申请已经帮您提交了，售后客服会尽快为您办理，"
    "后续进度会在这里同步给您。"
  )
  ai_msg = _save_ai_message(db, conv, answer, 0.9, [])
  _attach_meta(
    db, ai_msg,
    intent_label="操作类",
    plan_steps=[
      {"id": "hitl", "title": "买家确认", "status": "done", "detail": "买家已确认，退款建议已提交坐席审核", "demo": True}
    ],
    pending_confirmation=None,
    card=None,
    internal_note=(
      f"买家已确认提交：建议退款 ¥{payload.get('refund_amount', 0)}"
      f"（订单 {payload.get('order_id', 'DEMO')}），状态 pending_buyer → waiting_review，未自动打款。"
    ),
  )
  _clear_pending_meta(db, conv.id, confirmation_id)
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
      {"id": "hitl", "title": "买家确认", "status": "done", "detail": "买家已确认，退款建议已提交坐席审核", "demo": True}
    ],
    "pending_confirmation": None,
    "review_status": "waiting_review",
    "terminal_state": "waiting_review",
  }
