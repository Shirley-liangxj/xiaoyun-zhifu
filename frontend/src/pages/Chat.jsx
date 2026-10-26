import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getPublicConfig, getPublicConversation, getPublicOrders, publicChat, resolvePublicConversation, transferToHuman, confirmPublicAction } from '../api/public'

const STORAGE_KEY = 'xiaoyun_buyer_session'
const BOTTOM_THRESHOLD = 80

function roleMeta(role) {
  if (role === 'user') return { align: 'end', bubble: 'bg-primary text-white rounded-br-md', label: '' }
  if (role === 'agent') return { align: 'start', bubble: 'bg-emerald-50 text-emerald-900 shadow-sm rounded-bl-md', label: '人工客服' }
  return { align: 'start', bubble: 'bg-white text-gray-800 shadow-sm rounded-bl-md', label: 'AI 小云' }
}

// 买家端只渲染「客服说的话 + 订单卡片 + 一个操作按钮」
// 执行计划 / 工具调用 / 检索来源 / 置信度属于坐席视图，后端不下发
function OrderCard({ card }) {
  if (!card || card.type !== 'order') return null
  return (
    <div className="mt-2 rounded-xl border border-gray-100 bg-gray-50 overflow-hidden">
      <div className="flex items-center justify-between gap-2 px-2.5 py-1.5 bg-white border-b border-gray-100">
        <span className="text-[11px] text-gray-400">订单号 {card.order_id}</span>
        {card.status && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 shrink-0">
            {card.status}
          </span>
        )}
      </div>
      <div className="px-2.5 py-2">
        {card.product && <p className="text-xs font-medium text-gray-800">{card.product}</p>}
        {card.amount != null && (
          <p className="text-[11px] text-gray-500 mt-0.5">实付 ¥{Number(card.amount).toFixed(2)}</p>
        )}
        {(card.express || card.tracking_no) && (
          <p className="text-[11px] text-gray-500 mt-0.5">
            {card.express} {card.tracking_no}
          </p>
        )}
        {card.logistics && <p className="text-[11px] text-gray-400 mt-0.5">{card.logistics}</p>}
      </div>
    </div>
  )
}

function ActionBar({ action, loading, onConfirm }) {
  if (!action?.id) return null
  return (
    <div className="mt-2">
      <button
        type="button"
        disabled={loading}
        onClick={() => onConfirm(action.id)}
        className="w-full text-xs font-medium px-3 py-2 bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-60"
      >
        {action.label || '确认提交'}
      </button>
      <p className="text-[10px] text-gray-400 mt-1 text-center">提交后由客服跟进处理</p>
    </div>
  )
}

// 旅程阶段条：买家随时知道自己走到哪一步了（对齐国标「不得要求重复陈述、流程可见」）
function JourneyBar({ status, humanMode, hasMessages, canResolve, onResolve }) {
  if (!hasMessages) return null
  let label = 'AI 智能接待中'
  let cls = 'bg-emerald-50 text-emerald-700 border-emerald-200'
  if (status === 'closed') {
    label = '✓ 本次咨询已完成'
    cls = 'bg-gray-100 text-gray-500 border-gray-200'
  } else if (humanMode) {
    label = '人工客服处理中'
    cls = 'bg-sky-50 text-sky-700 border-sky-200'
  } else if (status === 'waiting_human') {
    label = '已转人工 · 排队接入中'
    cls = 'bg-orange-50 text-orange-700 border-orange-200'
  }
  return (
    <div className="shrink-0 px-4 py-1.5 border-b border-gray-100 flex items-center gap-2">
      <span className={`text-[11px] px-2 py-0.5 rounded-full border ${cls}`}>{label}</span>
      <span className="text-[10px] text-gray-300">售后咨询进度</span>
      {canResolve && (
        <button type="button" onClick={onResolve}
          className="ml-auto text-[11px] text-gray-400 hover:text-primary">结束咨询</button>
      )}
    </div>
  )
}

// 订单卡片（「我的订单」弹层内）：点击按钮直接发起，不再手输单号
function OrderItem({ order, disabled, onPick }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-medium text-gray-800 truncate">{order.product || order.order_id}</p>
        {order.status && (
          <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 shrink-0">{order.status}</span>
        )}
      </div>
      <p className="text-[11px] text-gray-400 mt-0.5">
        {order.order_id}{order.amount != null ? ` · ¥${Number(order.amount).toFixed(2)}` : ''}
      </p>
      {(order.express || order.tracking_no) && (
        <p className="text-[11px] text-gray-400">{order.express} {order.tracking_no}</p>
      )}
      <div className="flex gap-2 mt-2">
        <button type="button" disabled={disabled}
          onClick={() => onPick(`帮我查一下订单 ${order.order_id} 的物流`)}
          className="flex-1 text-[11px] py-1.5 border border-gray-200 text-gray-600 rounded-lg hover:border-primary hover:text-primary disabled:opacity-50">
          查物流
        </button>
        <button type="button" disabled={disabled}
          onClick={() => onPick(`我要退货 ${order.order_id}`)}
          className="flex-1 text-[11px] py-1.5 bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-50">
          申请退货
        </button>
      </div>
    </div>
  )
}

function fmtClock(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
}

function dayLabel(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const today = new Date()
  const sameDay = d.toDateString() === today.toDateString()
  if (sameDay) return '今天'
  return `${d.getMonth() + 1}月${d.getDate()}日`
}

function storageKey(companyId) {
  return companyId ? `${STORAGE_KEY}_${companyId}` : STORAGE_KEY
}

function loadSession(companyId) {
  try {
    return JSON.parse(localStorage.getItem(storageKey(companyId)) || 'null')
  } catch {
    return null
  }
}

function saveSession(companyId, data) {
  localStorage.setItem(storageKey(companyId), JSON.stringify(data))
}

const QUICK_QUESTIONS = [
  '我买的衣服尺码不合适能换货吗？',
  '退货需要自己付运费吗？',
  '退款多久能到账？',
  '发什么快递？',
]

export default function Chat() {
  const [searchParams] = useSearchParams()
  const companyIdParam = searchParams.get('company_id')
  const companyId = companyIdParam ? parseInt(companyIdParam, 10) : null
  const resolvedCompanyId = Number.isNaN(companyId) ? null : companyId
  const forceNew = searchParams.get('new') === '1'

  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [humanMode, setHumanMode] = useState(false)
  const [welcome, setWelcome] = useState('您好！我是智能客服小云，有什么可以帮您的？')
  const [shopName, setShopName] = useState('智能客服')
  const [activeCompanyId, setActiveCompanyId] = useState(resolvedCompanyId)
  const [nickname, setNickname] = useState('')
  const [nicknameInput, setNicknameInput] = useState('')
  const [ready, setReady] = useState(false)
  const [showFaq, setShowFaq] = useState(false)
  const [previousSession, setPreviousSession] = useState(null)
  const [showNewChat, setShowNewChat] = useState(false)
  const [newNickname, setNewNickname] = useState('')

  const [showJump, setShowJump] = useState(false)
  const [orders, setOrders] = useState([])
  const [showOrders, setShowOrders] = useState(false)
  const [convStatus, setConvStatus] = useState(null)
  const listRef = useRef(null)
  const atBottomRef = useRef(true)
  const lastCountRef = useRef(0)
  const loadingRef = useRef(false)

  useEffect(() => { loadingRef.current = loading }, [loading])

  const fetchOrders = (name) => {
    getPublicOrders(name, activeCompanyId)
      .then((res) => setOrders(Array.isArray(res.data) ? res.data : []))
      .catch(() => setOrders([]))
  }

  const scrollToBottom = (smooth = true) => {
    const el = listRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
    atBottomRef.current = true
    setShowJump(false)
  }

  const handleScroll = () => {
    const el = listRef.current
    if (!el) return
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < BOTTOM_THRESHOLD
    atBottomRef.current = near
    if (near) setShowJump(false)
  }

  useEffect(() => {
    getPublicConfig(resolvedCompanyId)
      .then((res) => {
        if (res.data.welcome_message) setWelcome(res.data.welcome_message)
        if (res.data.company_name) setShopName(`${res.data.company_name}客服`)
        if (res.data.company_id) setActiveCompanyId(res.data.company_id)
      })
      .catch(() => {})

    const saved = loadSession(resolvedCompanyId)
    if (!saved?.nickname) return
    setNickname(saved.nickname)
    setNicknameInput(saved.nickname)
    setNewNickname(saved.nickname)
    setReady(true)
    fetchOrders(saved.nickname)
    if (saved.conversationId) {
      if (forceNew) {
        // 从坐席台进来 = 新一次咨询；旧会话留一个「继续上次对话」入口
        setPreviousSession(saved.conversationId)
      } else {
        setConversationId(saved.conversationId)
      }
    }
  }, [resolvedCompanyId, forceNew])

  useEffect(() => {
    if (!ready) return
    // 只更新欢迎语，不冲掉已经拉回来的历史消息
    setMessages((prev) => {
      const body = prev.filter((m) => !m.isWelcome)
      return [{ role: 'assistant', content: welcome, isWelcome: true }, ...body]
    })
    lastCountRef.current = 1
    requestAnimationFrame(() => scrollToBottom(false))
  }, [welcome, ready])

  // 智能滚动：只在「本来就在底部」或「自己刚发消息」时跟到底，绝不打断上翻
  useEffect(() => {
    if (messages.length === lastCountRef.current) return
    const grew = messages.length > lastCountRef.current
    lastCountRef.current = messages.length
    if (!grew) return
    const last = messages[messages.length - 1]
    if (atBottomRef.current || last?.role === 'user' || loadingRef.current) {
      requestAnimationFrame(() => scrollToBottom(true))
    } else {
      setShowJump(true)
    }
  }, [messages])

  useEffect(() => {
    if (!conversationId || !ready) return undefined
    let cancelled = false
    const timer = setInterval(async () => {
      if (loadingRef.current) return
      try {
        const res = await getPublicConversation(conversationId, activeCompanyId)
        if (cancelled) return
        const data = res.data
        setHumanMode(!!data.human_mode)
        setConvStatus(data.status || null)
        const remote = (data.messages || []).map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          created_at: m.created_at,
          card: m.card || null,
          action: m.action || null,
        }))
        if (remote.length === 0) return
        setMessages((prev) => {
          const welcomeMsg = prev.find((m) => m.isWelcome)
          const prevBody = prev.filter((m) => !m.isWelcome)
          // 内容没变化就不更新，避免每 2.5 秒整表重渲染（也是「自动弹回最新」的另一半原因）
          if (JSON.stringify(prevBody) === JSON.stringify(remote)) return prev
          return welcomeMsg ? [welcomeMsg, ...remote] : remote
        })
      } catch {
        /* ignore */
      }
    }, 2500)
    return () => { cancelled = true; clearInterval(timer) }
  }, [conversationId, ready, activeCompanyId])

  const startWithNickname = (e) => {
    e.preventDefault()
    const name = nicknameInput.trim()
    if (!name) return
    setNickname(name)
    setNewNickname(name)
    saveSession(activeCompanyId, { nickname: name, conversationId: null })
    setConversationId(null)
    setConvStatus(null)
    setHumanMode(false)
    setReady(true)
    setMessages([{ role: 'assistant', content: welcome, isWelcome: true }])
    lastCountRef.current = 1
    fetchOrders(name)
  }

  const resetToNewChat = (name) => {
    const finalName = (name || nickname || '').trim()
    if (!finalName) return
    setNickname(finalName)
    setNicknameInput(finalName)
    setNewNickname(finalName)
    saveSession(activeCompanyId, { nickname: finalName, conversationId: null })
    setConversationId(null)
    setConvStatus(null)
    setHumanMode(false)
    setShowFaq(false)
    setShowNewChat(false)
    setShowOrders(false)
    setPreviousSession(null)
    setMessages([{ role: 'assistant', content: welcome, isWelcome: true }])
    lastCountRef.current = 1
    fetchOrders(finalName)
    requestAnimationFrame(() => scrollToBottom(false))
  }

  const resumePrevious = () => {
    if (!previousSession) return
    setConversationId(previousSession)
    setPreviousSession(null)
    saveSession(activeCompanyId, { nickname, conversationId: previousSession })
  }

  const appendAssistant = (data) => {
    setConversationId(data.conversation_id)
    saveSession(activeCompanyId, { nickname, conversationId: data.conversation_id })
    setHumanMode(!!data.human_mode || (!!data.need_human && !data.action))
    if (!data.answer && !data.card) return
    setMessages((prev) => [...prev, {
      id: data.message_id,
      role: 'assistant',
      content: data.answer || '',
      need_human: data.need_human,
      card: data.card || null,
      action: data.action || null,
      created_at: new Date().toISOString(),
    }])
  }

  const handleConfirm = async (confirmationId) => {
    if (!confirmationId || loading) return
    setLoading(true)
    try {
      const res = await confirmPublicAction(confirmationId, conversationId, nickname, activeCompanyId)
      appendAssistant(res.data)
    } catch {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: '确认失败，请稍后再试或转人工。',
        error: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  const sendMessage = async (text) => {
    const userMsg = (text || '').trim()
    if (!userMsg || loading || convStatus === 'closed') return
    setInput('')
    setShowFaq(false)
    setShowOrders(false)
    setMessages((prev) => [...prev, {
      role: 'user',
      content: userMsg,
      created_at: new Date().toISOString(),
    }])
    setLoading(true)
    try {
      const res = await publicChat(userMsg, conversationId, nickname, activeCompanyId)
      appendAssistant(res.data)
    } catch {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: '抱歉，服务暂时不可用，请稍后再试。',
        error: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  const handleSend = (e) => {
    e.preventDefault()
    sendMessage(input)
  }

  const handleResolve = async () => {
    if (!conversationId || loading || convStatus === 'closed') return
    setLoading(true)
    try {
      const res = await resolvePublicConversation(conversationId, nickname, activeCompanyId)
      setConvStatus('closed')
      setHumanMode(false)
      setMessages((prev) => [...prev, {
        id: res.data.message_id,
        role: 'assistant',
        content: res.data.answer,
        created_at: new Date().toISOString(),
      }])
      requestAnimationFrame(() => scrollToBottom(true))
    } catch {
      /* ignore */
    } finally {
      setLoading(false)
    }
  }

  const handleTransfer = async () => {
    setLoading(true)
    setShowFaq(false)
    try {
      const res = await transferToHuman(conversationId, nickname, activeCompanyId)
      appendAssistant(res.data)
    } catch {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: '转接失败，请稍后再试。',
        error: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  const pickFaq = (q) => {
    setInput(q)
    setShowFaq(false)
  }

  if (!ready) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
        <div className="w-full max-w-[390px] bg-white rounded-3xl shadow-2xl p-6 border border-gray-200">
          <div className="text-center mb-6">
            <div className="w-12 h-12 rounded-full bg-primary/10 text-primary flex items-center justify-center mx-auto mb-3 text-lg">云</div>
            <h1 className="text-lg font-semibold text-gray-800">{shopName}</h1>
            <p className="text-xs text-gray-400 mt-1">请输入昵称后开始咨询（坐席端将显示此名称）</p>
          </div>
          <form onSubmit={startWithNickname} className="space-y-4">
            <input
              required
              value={nicknameInput}
              onChange={(e) => setNicknameInput(e.target.value)}
              placeholder="如：王女士"
              maxLength={20}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary"
            />
            <button type="submit" className="w-full py-2.5 bg-primary text-white rounded-xl text-sm hover:bg-primary-dark">
              开始咨询
            </button>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
      <div className="w-full max-w-[390px] h-[720px] bg-white rounded-3xl shadow-2xl flex flex-col overflow-hidden border border-gray-200 relative">
        <div className="bg-primary px-4 py-3 flex items-center gap-3 shrink-0">
          <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-white text-sm">云</div>
          <div className="flex-1 min-w-0">
            <p className="text-white text-sm font-semibold">{shopName}</p>
            <p className="text-white/70 text-xs">
              {humanMode ? '人工客服处理中' : 'AI 智能客服 · 在线'} · {nickname}
            </p>
          </div>
          <button type="button" onClick={() => { setNewNickname(nickname); setShowNewChat(true) }}
            className="text-xs text-white/90 border border-white/30 px-2 py-1 rounded-full hover:bg-white/10">
            新咨询
          </button>
        </div>

        {previousSession && !conversationId && (
          <div className="shrink-0 px-4 py-2 bg-amber-50 border-b border-amber-100 flex items-center justify-between gap-2">
            <p className="text-[11px] text-amber-700">这是新一次咨询</p>
            <button type="button" onClick={resumePrevious} className="text-[11px] text-primary hover:underline shrink-0">
              继续上次对话 →
            </button>
          </div>
        )}

        <JourneyBar
          status={convStatus}
          humanMode={humanMode}
          hasMessages={messages.length > 1}
          canResolve={!!conversationId && convStatus !== 'closed'}
          onResolve={handleResolve}
        />

        <div className="relative flex-1 min-h-0">
          <div ref={listRef} onScroll={handleScroll} className="absolute inset-0 overflow-y-auto p-4 space-y-3 bg-gray-50">
            {messages.map((msg, i) => {
              const meta = roleMeta(msg.role)
              const prev = messages[i - 1]
              const showDay = msg.created_at && (!prev?.created_at || dayLabel(msg.created_at) !== dayLabel(prev.created_at))
              return (
                <div key={`${msg.id ?? 'tmp'}-${i}`}>
                  {showDay && msg.created_at && (
                    <p className="text-center text-[10px] text-gray-400 my-1">{dayLabel(msg.created_at)}</p>
                  )}
                  <div className={`flex ${meta.align === 'end' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${meta.bubble}`}>
                      {meta.label && !msg.isWelcome && (
                        <p className="text-xs opacity-50 mb-1">{meta.label}</p>
                      )}
                      <p className="whitespace-pre-wrap">{msg.content}</p>

                      <OrderCard card={msg.card} />

                      <ActionBar action={msg.action} loading={loading} onConfirm={handleConfirm} />

                      {msg.created_at && (
                        <p className={`text-[10px] mt-1 ${msg.role === 'user' ? 'text-white/60 text-right' : 'text-gray-300'}`}>
                          {fmtClock(msg.created_at)}
                        </p>
                      )}

                      {msg.need_human && humanMode && !msg.action && (
                        <div className="mt-2 px-2 py-1.5 bg-orange-50 border border-orange-200 rounded-lg text-xs text-orange-700">
                          已进入人工队列，坐席回复后会显示在这里
                        </div>
                      )}

                      {msg.need_human && !humanMode && !msg.action && msg.role === 'assistant' && !msg.isWelcome && (
                        <button
                          type="button"
                          onClick={handleTransfer}
                          disabled={loading}
                          className="mt-2 block w-full text-left text-xs px-2 py-1.5 bg-orange-50 border border-orange-200 rounded-lg text-orange-700 hover:bg-orange-100 disabled:opacity-60"
                        >
                          这个回答不满意？转人工客服
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-white rounded-2xl px-4 py-3 shadow-sm text-sm text-gray-400">
                  {humanMode ? '消息已送达坐席...' : '小云正在思考...'}
                </div>
              </div>
            )}
          </div>

          {showJump && (
            <button
              type="button"
              onClick={() => scrollToBottom(true)}
              className="absolute left-1/2 -translate-x-1/2 bottom-3 px-3 py-1.5 bg-primary text-white text-xs rounded-full shadow-lg"
            >
              有新消息 ↓
            </button>
          )}
        </div>

        {showFaq && (
          <div className="absolute inset-x-0 bottom-16 mx-3 mb-1 bg-white rounded-2xl shadow-xl border border-gray-100 p-3 z-10">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-gray-700">常见问题</p>
              <button type="button" onClick={() => setShowFaq(false)} className="text-xs text-gray-400">关闭</button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {QUICK_QUESTIONS.map((q) => (
                <button key={q} type="button" onClick={() => pickFaq(q)}
                  className="text-xs px-2.5 py-1.5 bg-gray-50 border border-gray-200 rounded-full text-gray-600 hover:border-primary hover:text-primary">
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {showOrders && (
          <div className="absolute inset-x-0 bottom-16 mx-3 mb-1 bg-white rounded-2xl shadow-xl border border-gray-100 p-3 z-10 max-h-[55%] overflow-y-auto">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-gray-700">我的订单</p>
              <button type="button" onClick={() => setShowOrders(false)} className="text-xs text-gray-400">关闭</button>
            </div>
            {orders.length === 0 ? (
              <p className="text-[11px] text-gray-400 py-2">暂未找到关联订单</p>
            ) : (
              <div className="space-y-2">
                {orders.map((o) => (
                  <OrderItem
                    key={o.order_id}
                    order={o}
                    disabled={convStatus === 'closed'}
                    onPick={(t) => { setShowOrders(false); sendMessage(t) }}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        <form onSubmit={handleSend} className="p-3 border-t border-gray-100 flex gap-2 bg-white items-center shrink-0">
          <button type="button" onClick={() => setShowFaq((v) => !v)}
            className="shrink-0 text-xs px-2 py-2 border border-gray-200 text-gray-600 rounded-full hover:bg-gray-50"
            title="常见问题">
            常见
          </button>
          <button type="button" onClick={() => setShowOrders((v) => !v)}
            className="shrink-0 text-xs px-2 py-2 border border-gray-200 text-gray-600 rounded-full hover:bg-gray-50"
            title="我的订单">
            订单
          </button>
          {!humanMode && (
            <button type="button" onClick={handleTransfer} disabled={loading}
              className="shrink-0 text-xs px-2 py-2 border border-orange-200 text-orange-600 rounded-full hover:bg-orange-50 disabled:opacity-60">
              转人工
            </button>
          )}
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={humanMode ? '向人工客服描述问题...' : '输入您的问题...'}
            className="flex-1 min-w-0 px-4 py-2.5 bg-gray-50 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button type="submit" disabled={loading}
            className="shrink-0 w-10 h-10 bg-primary text-white rounded-full flex items-center justify-center hover:bg-primary-dark disabled:opacity-60">
            ↑
          </button>
        </form>

        {showNewChat && (
          <div className="absolute inset-0 bg-black/40 flex items-center justify-center p-5 z-20">
            <div className="w-full bg-white rounded-2xl p-5 shadow-xl">
              <h3 className="text-sm font-semibold text-gray-800 mb-1">开始新咨询</h3>
              <p className="text-xs text-gray-400 mb-3">可换一个昵称，模拟另一位买家进线</p>
              <input
                value={newNickname}
                onChange={(e) => setNewNickname(e.target.value)}
                maxLength={20}
                placeholder="如：李先生"
                className="w-full px-3 py-2 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-primary mb-3"
              />
              <div className="flex gap-2">
                <button type="button" onClick={() => setShowNewChat(false)}
                  className="flex-1 py-2 text-sm text-gray-600 border border-gray-200 rounded-xl hover:bg-gray-50">
                  取消
                </button>
                <button type="button" onClick={() => resetToNewChat(newNickname)}
                  className="flex-1 py-2 text-sm text-white bg-primary rounded-xl hover:bg-primary-dark">
                  开始
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
