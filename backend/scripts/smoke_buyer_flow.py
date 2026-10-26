"""本地回归：验证买家端多轮上下文 / 消息元数据 / 客户信息卡

不依赖真实大模型：临时替换 llm_service.complete，记录模型实际收到的 messages。
"""
import json
import os
import sys
import tempfile

WORK = tempfile.mkdtemp(prefix="xytest_")
os.chdir(WORK)
sys.path.insert(0, r"D:\codex\xiaoyun-github-sync-20261014\backend")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.llm import LLMResult, llm_service  # noqa: E402

calls = []
FAKE_REPLY = {"text": "好的，请问您的订单号是多少呢？"}


def fake_complete(messages, temperature=0.7, tools=None, tool_choice=None):
  calls.append({"messages": json.loads(json.dumps(messages, ensure_ascii=False))})
  return LLMResult(content=FAKE_REPLY["text"], tool_calls=[], usage={}, latency_ms=1)


llm_service.complete = fake_complete

failures = []


def check(name, cond, extra=""):
  print(("PASS  " if cond else "FAIL  ") + name + ("" if cond else f"  <- {extra}"))
  if not cond:
    failures.append(name)


with TestClient(app) as client:
  # ---------- 1. 多轮上下文 ----------
  r1 = client.post("/api/public/chat", json={"message": "订单要退货", "customer_name": "测试买家"})
  check("第一轮返回 200", r1.status_code == 200, r1.text[:300])
  data1 = r1.json()
  conv_id = data1["conversation_id"]

  r2 = client.post("/api/public/chat", json={
    "message": "demo-1002", "conversation_id": conv_id, "customer_name": "测试买家",
  })
  check("第二轮返回 200", r2.status_code == 200, r2.text[:300])

  msgs2 = calls[-1]["messages"]
  roles = [m["role"] for m in msgs2]
  check("第二轮把历史带给了模型", len(msgs2) >= 4, f"roles={roles}")
  check("历史里包含用户上一句「订单要退货」",
        any(m["role"] == "user" and "订单要退货" in m["content"] for m in msgs2), str(msgs2))
  check("历史里包含助手上一句回答",
        any(m["role"] == "assistant" and "订单号" in m["content"] for m in msgs2), str(msgs2))
  last_user = [m for m in msgs2 if m["role"] == "user"][-1]["content"]
  check("最后一轮带上了承接提示", "对话上下文提示" in last_user, last_user)

  # ---------- 2. 消息元数据持久化 ----------
  detail = client.get(f"/api/public/conversations/{conv_id}").json()
  msgs = detail["messages"]
  check("买家端能拉到消息", len(msgs) >= 3, str(len(msgs)))
  ai_msgs = [m for m in msgs if m["role"] == "assistant"]
  check("AI 消息带 plan_steps 字段", all("plan_steps" in m for m in ai_msgs))
  check("直接回答产生了执行计划", any(m["plan_steps"] for m in ai_msgs),
        str([m["plan_steps"] for m in ai_msgs]))
  check("AI 消息带 intent_label", any(m.get("intent_label") for m in ai_msgs),
        str([m.get("intent_label") for m in ai_msgs]))

  # ---------- 3. 坐席端登录 + 会话 / 客户信息卡 ----------
  login = client.post("/api/auth/login", json={"username": "testadmin", "password": "123456"})
  check("演示账号可登录", login.status_code == 200, login.text[:200])
  token = login.json().get("access_token")
  headers = {"Authorization": f"Bearer {token}"}

  convs = client.get("/api/conversations/", headers=headers).json()
  check("会话列表可拉取", isinstance(convs, list) and len(convs) > 0)
  target = next((c for c in convs if c["id"] == conv_id), convs[0])

  prof = client.get(f"/api/conversations/{target['id']}/profile", headers=headers)
  check("客户信息卡接口可用", prof.status_code == 200, prof.text[:300])
  p = prof.json()
  check("客户信息卡含进线次数", isinstance(p.get("total_conversations"), int), str(p))
  check("客户信息卡含订单列表", isinstance(p.get("orders"), list), str(p.get("orders"))[:200])

  # ---------- 4. 内部备注不下发买家端 ----------
  note = client.post(
    f"/api/conversations/{target['id']}/messages",
    json={"content": "内部备注测试：该客户已三次进线", "role": "agent", "is_internal": True},
    headers=headers,
  )
  check("内部备注可写入", note.status_code == 200, note.text[:300])
  buyer_view = client.get(f"/api/public/conversations/{target['id']}").json()
  check("内部备注不出现在买家端",
        all("内部备注测试" not in m["content"] for m in buyer_view["messages"]),
        str([m["content"][:20] for m in buyer_view["messages"]]))

print()
print("=" * 50)

# ---------- 5. 退款链路 + HITL 确认单在轮询后是否还在 ----------
script = [
  {"tool": "query_order", "args": {"order_id": "DEMO-1002"}},
  {"tool": "calc_refund", "args": {"order_id": "DEMO-1002", "amount": 268, "days_since_purchase": 5}},
]
seen_roles = []


def scripted_complete(messages, temperature=0.7, tools=None, tool_choice=None):
  seen_roles.append([m["role"] for m in messages])
  if script:
    step = script.pop(0)
    return LLMResult(
      content="",
      tool_calls=[{
        "id": f"call_{len(seen_roles)}",
        "type": "function",
        "function": {"name": step["tool"], "arguments": json.dumps(step["args"])},
      }],
      usage={}, latency_ms=1,
    )
  return LLMResult(content="已为您试算退款，请确认。", tool_calls=[], usage={}, latency_ms=1)


llm_service.complete = scripted_complete

with TestClient(app) as client:
  first = client.post("/api/public/chat", json={"message": "订单DEMO-1002我要申请退款", "customer_name": "退款买家"})
  check("退款链路首轮 200", first.status_code == 200, first.text[:300])
  d = first.json()
  cid = d["conversation_id"]

  check("退款链路产生了待确认动作", bool(d.get("pending_confirmation")), str(d)[:400])
  check("待确认金额为 268", (d.get("pending_confirmation") or {}).get("payload", {}).get("refund_amount") == 268.0,
        str(d.get("pending_confirmation")))
  check("回复包含试算金额", "268" in d.get("answer", ""), d.get("answer", "")[:200])
  check("退款走了 HITL 中断", any(s.get("id") == "hitl" for s in d.get("plan_steps", [])), str(d.get("plan_steps")))

  # 轮询接口 = 买家端每 2.5 秒拉的那次，确认单和订单卡片必须还在
  polled = client.get(f"/api/public/conversations/{cid}").json()
  ai_msgs = [m for m in polled["messages"] if m["role"] == "assistant"]
  hitl_msg = next((m for m in ai_msgs if m.get("pending_confirmation")), None)
  check("轮询后确认按钮仍在（不再闪一下就没）", hitl_msg is not None, str(ai_msgs)[:400])
  check("轮询后订单卡片仍在", any(m.get("card") for m in ai_msgs), str([m.get("card") for m in ai_msgs])[:300])
  check("轮询后执行计划仍在", any(m.get("plan_steps") for m in ai_msgs))

  # 确认后，按钮应消失
  if hitl_msg:
    cid_confirm = hitl_msg["pending_confirmation"]["id"]
    conf = client.post("/api/public/confirm", json={
      "confirmation_id": cid_confirm, "conversation_id": cid, "customer_name": "退款买家",
    })
    check("确认接口可用", conf.status_code == 200, conf.text[:300])
    after = client.get(f"/api/public/conversations/{cid}").json()
    still = [m for m in after["messages"] if (m.get("pending_confirmation") or {}).get("id") == cid_confirm]
    check("确认后按钮消失，不能重复点", len(still) == 0, str(len(still)))

print()
print("=" * 50)
print(f"结果：{' 全部通过' if not failures else ' 失败 ' + ', '.join(failures)}")
sys.exit(1 if failures else 0)
