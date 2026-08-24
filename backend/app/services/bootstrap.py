"""演示数据与新租户知识库初始化"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.data.knowledge_seed import KNOWLEDGE_DOCS, QUICK_REPLIES
from app.models import (
  Company,
  CompanySettings,
  Conversation,
  KnowledgeDoc,
  Message,
  QuickReply,
  Ticket,
  User,
)
from app.services.rag import rebuild_company_index
from app.services.settings import get_or_create_settings


def seed_knowledge(db: Session, company_id: int, replace: bool = False) -> int:
  """灌入默认售后政策。replace=True 时先清空该公司文档。"""
  if replace:
    db.query(KnowledgeDoc).filter(KnowledgeDoc.company_id == company_id).delete()
    db.commit()
  elif db.query(KnowledgeDoc).filter(KnowledgeDoc.company_id == company_id).first():
    return 0

  for doc in KNOWLEDGE_DOCS:
    db.add(KnowledgeDoc(
      company_id=company_id,
      title=doc["title"],
      content=doc["content"],
      category=doc["category"],
    ))
  db.commit()
  return len(KNOWLEDGE_DOCS)


def seed_quick_replies(db: Session, company_id: int, replace: bool = False) -> int:
  if replace:
    db.query(QuickReply).filter(QuickReply.company_id == company_id).delete()
    db.commit()
  elif db.query(QuickReply).filter(QuickReply.company_id == company_id).first():
    return 0

  for item in QUICK_REPLIES:
    db.add(QuickReply(company_id=company_id, **item))
  db.commit()
  return len(QUICK_REPLIES)


def seed_tenant_defaults(db: Session, company_id: int) -> None:
  """新公司：设置 + 知识库 + 话术，并尝试建索引。"""
  get_or_create_settings(db, company_id)
  seed_knowledge(db, company_id, replace=False)
  seed_quick_replies(db, company_id, replace=False)
  try:
    rebuild_company_index(db, company_id)
  except Exception:
    pass


def seed_conversations(db: Session, company_id: int, user_id: int) -> dict[str, int]:
  """创建演示会话，返回客户名 -> 会话ID。"""
  convs = db.query(Conversation).filter(Conversation.company_id == company_id).all()
  for conv in convs:
    db.query(Message).filter(Message.conversation_id == conv.id).delete()
  db.query(Conversation).filter(Conversation.company_id == company_id).delete()
  db.commit()

  scenarios = [
    {
      "customer_name": "李女士",
      "channel": "wechat",
      "status": "closed",
      "messages": [
        ("customer", "我买的连衣裙尺码偏大了，能换小一码吗？"),
        ("ai_suggestion", "亲，尺码不合适可以在签收后15天内申请换货哦。请保持商品完好、吊牌未剪，寄回运费需您承担，我们承担换出运费。", 0.82, '[{"title":"退换货政策","category":"退换货","score":0.85}]'),
        ("agent", "李女士您好，已为您登记换货申请，请将商品寄回到：浙江省杭州市余杭区xx路xx号，寄出后把单号发我即可~"),
      ],
    },
    {
      "customer_name": "王先生",
      "channel": "web",
      "status": "closed",
      "messages": [
        ("customer", "我的快递怎么还没到？都5天了"),
        ("ai_suggestion", "亲，正常情况下江浙沪2-3天、其他地区3-5天送达。超过7天未更新请联系客服查询。", 0.75, '[{"title":"物流说明","category":"物流","score":0.78}]'),
        ("agent", "王先生您好，我帮您查了一下，包裹目前在途中，预计明天送达。给您带来不便非常抱歉！"),
      ],
    },
    {
      "customer_name": "赵小姐",
      "channel": "wechat",
      "status": "waiting_human",
      "messages": [
        ("customer", "收到的衣服有线头，质量太差了"),
        ("ai_suggestion", "非常抱歉！开线脱线属于质量问题，您可申请退货退款，运费由我们承担。请提供照片凭证。", 0.88, '[{"title":"质量问题处理","category":"售后政策","score":0.91}]'),
      ],
    },
    {
      "customer_name": "陈先生",
      "channel": "phone",
      "status": "closed",
      "messages": [
        ("customer", "退款什么时候能到账？已经寄回去3天了"),
        ("ai_suggestion", "退款审核通过后：支付宝/微信1-3个工作日，银行卡3-7个工作日到账。商家签收后3个工作日内发起退款。", 0.79, '[{"title":"退款时效","category":"支付","score":0.82}]'),
        ("agent", "陈先生您好，您的退款已处理完成，预计1-2个工作日内到账，请注意查收~"),
      ],
    },
    {
      "customer_name": "刘女士",
      "channel": "web",
      "status": "active",
      "messages": [
        ("customer", "我想改一下收货地址，还没发货"),
        ("ai_suggestion", "未发货订单可在订单详情修改地址。已发货订单需联系快递改址，可能产生费用。", 0.71, '[{"title":"常见FAQ","category":"通用","score":0.74}]'),
        ("agent", "刘女士您好，已帮您修改收货地址为新地址，请确认是否正确~"),
      ],
    },
  ]

  name_to_id: dict[str, int] = {}
  for scenario in scenarios:
    conv = Conversation(
      company_id=company_id,
      customer_name=scenario["customer_name"],
      channel=scenario["channel"],
      status=scenario["status"],
    )
    db.add(conv)
    db.flush()
    name_to_id[scenario["customer_name"]] = conv.id
    for msg in scenario["messages"]:
      role = msg[0]
      content = msg[1]
      kwargs = {
        "conversation_id": conv.id,
        "role": role,
        "content": content,
        "is_sent": True,
      }
      if role == "ai_suggestion":
        kwargs["confidence"] = msg[2]
        kwargs["sources"] = msg[3]
        # 待人工会话里的 AI 回复作为待采纳建议
        if scenario["status"] == "waiting_human":
          kwargs["is_sent"] = False
      if role == "agent":
        kwargs["sender_id"] = user_id
      db.add(Message(**kwargs))
  db.commit()
  return name_to_id


def seed_tickets(db: Session, company_id: int, user_id: int, conv_ids: dict[str, int]) -> int:
  db.query(Ticket).filter(Ticket.company_id == company_id).delete()
  db.commit()
  tickets = [
    {
      "title": "李女士换货申请",
      "description": "连衣裙M码偏大，申请换S码",
      "status": "resolved",
      "priority": "normal",
      "conversation_id": conv_ids.get("李女士"),
    },
    {
      "title": "赵小姐质量问题投诉",
      "description": "收到衣服有多处线头，要求退货退款",
      "status": "in_progress",
      "priority": "high",
      "conversation_id": conv_ids.get("赵小姐"),
    },
    {
      "title": "王先生物流超时",
      "description": "快递5天未送达，客户催促",
      "status": "open",
      "priority": "urgent",
      "conversation_id": conv_ids.get("王先生"),
    },
  ]
  for item in tickets:
    db.add(Ticket(company_id=company_id, assignee_id=user_id, **item))
  db.commit()
  return len(tickets)


def ensure_company_and_user(db: Session) -> tuple[Company, User]:
  company = db.query(Company).filter(Company.id == 1).first()
  if not company:
    company = Company(id=1, name="云裳服饰有限公司", industry="服饰")
    db.add(company)
    db.flush()

  user = db.query(User).filter(User.username == "testadmin").first()
  if not user:
    user = User(
      username="testadmin",
      email="admin@yunshang.com",
      hashed_password=hash_password("123456"),
      display_name="张客服",
      role="admin",
      company_id=company.id,
    )
    db.add(user)
  db.commit()
  return company, user


def seed_minimal_demo(db: Session, company_id: int, user_id: int) -> bool:
  """新租户：若无会话则创建 1 条待人工演示会话 + 1 条工单。"""
  if db.query(Conversation).filter(Conversation.company_id == company_id).first():
    return False

  conv = Conversation(
    company_id=company_id,
    customer_name="演示买家",
    channel="web",
    status="waiting_human",
  )
  db.add(conv)
  db.flush()
  db.add(Message(
    conversation_id=conv.id,
    role="customer",
    content="收到的衣服有线头，质量太差了，能退吗？",
    is_sent=True,
  ))
  db.add(Message(
    conversation_id=conv.id,
    role="ai_suggestion",
    content="非常抱歉！开线脱线属于质量问题，您可申请退货退款，运费由我们承担。请提供照片凭证。",
    confidence=0.88,
    sources='[{"title":"质量问题处理","category":"售后政策","score":0.91}]',
    is_sent=False,
  ))
  db.add(Ticket(
    company_id=company_id,
    assignee_id=user_id,
    title="演示买家质量问题",
    description="收到衣服有线头，要求退货退款",
    status="open",
    priority="high",
    conversation_id=conv.id,
  ))
  db.commit()
  return True


def reset_demo_data_for_company(db: Session, company_id: int, user_id: int) -> None:
  """为指定租户重建演示数据（知识库、话术、会话、工单）。"""
  get_or_create_settings(db, company_id)
  seed_knowledge(db, company_id, replace=True)
  seed_quick_replies(db, company_id, replace=True)
  conv_ids = seed_conversations(db, company_id, user_id)
  seed_tickets(db, company_id, user_id, conv_ids)
  try:
    rebuild_company_index(db, company_id)
  except Exception:
    pass


def reset_demo_data(db: Session) -> None:
  """手动脚本：重建演示租户全部样例数据。"""
  company, user = ensure_company_and_user(db)
  reset_demo_data_for_company(db, company.id, user.id)


def ensure_demo_data_if_empty(db: Session) -> bool:
  """启动时若没有任何用户，则灌入演示账号与知识库。"""
  if db.query(User).first():
    return False
  reset_demo_data(db)
  return True
