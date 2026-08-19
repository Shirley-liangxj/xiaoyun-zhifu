"""数据初始化脚本 - 知识库、会话、工单、话术"""
import json
import os
import sys

# 确保能导入 app 包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.security import hash_password
from app.data.knowledge_seed import KNOWLEDGE_DOCS, QUICK_REPLIES
from app.database import Base, SessionLocal, engine
import app.models  # noqa: F401 - 注册全部 ORM 表
from app.models import (
  Company, CompanySettings, Conversation, KnowledgeDoc, Message,
  QuickReply, Ticket, User,
)
from app.services.rag import rebuild_company_index

# 清除旧 FAISS 索引（embedding 维度可能变化）
import shutil
from app.core.config import settings
DEMO_PASSWORD = os.getenv("XIAOYUN_DEMO_PASSWORD", "ChangeMeBeforeDeploy!")
if os.path.exists(settings.FAISS_DATA_DIR):
  shutil.rmtree(settings.FAISS_DATA_DIR)


def ensure_company_and_user(db):
  """确保默认公司和测试账号存在"""
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
      hashed_password=hash_password("DEMO_PASSWORD"),
      display_name="张客服",
      role="admin",
      company_id=company.id,
    )
    db.add(user)
  db.commit()
  return company, user


def seed_knowledge(db, company_id):
  """灌入知识库文档"""
  db.query(KnowledgeDoc).filter(KnowledgeDoc.company_id == company_id).delete()
  db.commit()
  for doc in KNOWLEDGE_DOCS:
    db.add(KnowledgeDoc(company_id=company_id, title=doc["title"], content=doc["content"], category=doc["category"]))
  db.commit()
  print(f"  知识库: {len(KNOWLEDGE_DOCS)} 篇文档")


def seed_quick_replies(db, company_id):
  db.query(QuickReply).filter(QuickReply.company_id == company_id).delete()
  db.commit()
  for r in QUICK_REPLIES:
    db.add(QuickReply(company_id=company_id, **r))
  db.commit()
  print(f"  话术库: {len(QUICK_REPLIES)} 条")


def seed_conversations(db, company_id, user_id):
  """创建5个历史会话"""
  # 清除旧数据
  convs = db.query(Conversation).filter(Conversation.company_id == company_id).all()
  for c in convs:
    db.query(Message).filter(Message.conversation_id == c.id).delete()
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
      "status": "active",
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

  for s in scenarios:
    conv = Conversation(
      company_id=company_id,
      customer_name=s["customer_name"],
      channel=s["channel"],
      status=s["status"],
    )
    db.add(conv)
    db.flush()
    for msg in s["messages"]:
      role = msg[0]
      content = msg[1]
      kwargs = {"conversation_id": conv.id, "role": role, "content": content, "is_sent": True}
      if role == "ai_suggestion":
        kwargs["confidence"] = msg[2]
        kwargs["sources"] = msg[3]
      if role == "agent":
        kwargs["sender_id"] = user_id
      db.add(Message(**kwargs))
  db.commit()
  print(f"  会话: {len(scenarios)} 个")


def seed_tickets(db, company_id, user_id):
  db.query(Ticket).filter(Ticket.company_id == company_id).delete()
  db.commit()
  tickets = [
    {"title": "李女士换货申请", "description": "连衣裙M码偏大，申请换S码", "status": "resolved", "priority": "normal"},
    {"title": "赵小姐质量问题投诉", "description": "收到衣服有多处线头，要求退货退款", "status": "in_progress", "priority": "high"},
    {"title": "王先生物流超时", "description": "快递5天未送达，客户催促", "status": "open", "priority": "urgent"},
  ]
  for t in tickets:
    db.add(Ticket(company_id=company_id, assignee_id=user_id, **t))
  db.commit()
  print(f"  工单: {len(tickets)} 个")


def main():
  print("=== 小云智服数据初始化 ===")
  Base.metadata.create_all(bind=engine)
  db = SessionLocal()
  try:
    company, user = ensure_company_and_user(db)
    cid, uid = company.id, user.id

    # 确保设置存在
    if not db.query(CompanySettings).filter(CompanySettings.company_id == cid).first():
      db.add(CompanySettings(company_id=cid))
      db.commit()

    seed_knowledge(db, cid)
    seed_quick_replies(db, cid)
    seed_conversations(db, cid, uid)
    seed_tickets(db, cid, uid)

    print("  正在重建向量索引（embedding-3）...")
    count = rebuild_company_index(db, cid)
    print(f"  索引完成: {count} 篇")

    print("=== 初始化完成 ===")
    print("  账号: testadmin （密码见环境变量 XIAOYUN_DEMO_PASSWORD，部署前请修改默认密码）")
    print("  买家端: http://localhost:5173/chat")
  finally:
    db.close()


if __name__ == "__main__":
  main()
