import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import { getPublicConfig, getPublicConversation, publicChat, transferToHuman } from '../api/public'

const STORAGE_KEY = 'xiaoyun_buyer_session'

function roleMeta(role) {
  if (role === 'user') return { align: 'end', bubble: 'bg-primary text-white rounded-br-md', label: '' }
  if (role === 'agent') return { align: 'start', bubble: 'bg-emerald-50 text-emerald-900 shadow-sm rounded-bl-md', label: '人工客服' }
  return { align: 'start', bubble: 'bg-white text-gray-800 shadow-sm rounded-bl-md', label: 'AI 小云' }
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
  const endRef = useRef(null)

  useEffect(() => {
    getPublicConfig(resolvedCompanyId)
      .then((res) => {
        if (res.data.welcome_message) setWelcome(res.data.welcome_message)
        if (res.data.company_name) setShopName(`${res.data.company_name}客服`)
        if (res.data.company_id) setActiveCompanyId(res.data.company_id)
      })
      .catch(() => {})

    const saved = loadSession(resolvedCompanyId)
    if (saved?.nickname) {
      setNickname(saved.nickname)
      setNicknameInput(saved.nickname)
      if (saved.conversationId) setConversationId(saved.conversationId)
      setReady(true)
    }
  }, [resolvedCompanyId])

  useEffect(() => {
    if (!ready) return
    setMessages([{ role: 'assistant', content: welcome, isWelcome: true }])
  }, [welcome, ready])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  useEffect(() => {
    if (!conversationId || !ready) return undefined
    const timer = setInterval(async () => {
      try {
        const res = await getPublicConversation(conversationId, activeCompanyId)
        const data = res.data
        setHumanMode(!!data.human_mode)
        const remote = (data.messages || []).map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          sources: m.sources,
          need_human: false,
        }))
        if (remote.length === 0) return
        setMessages((prev) => {
          const welcomeMsg = prev.find((m) => m.isWelcome)
          const prevMap = new Map(prev.filter((m) => m.id).map((m) => [m.id, m]))
          const merged = remote.map((m) => ({
            ...m,
            need_human: prevMap.get(m.id)?.need_human ?? false,
          }))
          return welcomeMsg ? [welcomeMsg, ...merged] : merged
        })
      } catch {
        /* ignore */
      }
    }, 2500)
    return () => clearInterval(timer)
  }, [conversationId, ready, activeCompanyId])

  const startWithNickname = (e) => {
    e.preventDefault()
    const name = nicknameInput.trim()
    if (!name) return
    setNickname(name)
    saveSession(activeCompanyId, { nickname: name, conversationId: null })
    setConversationId(null)
    setHumanMode(false)
    setReady(true)
    setMessages([{ role: 'assistant', content: welcome, isWelcome: true }])
  }

  const startNewConsult = () => {
    saveSession(activeCompanyId, { nickname, conversationId: null })
    setConversationId(null)
    setHumanMode(false)
    setMessages([{ role: 'assistant', content: welcome, isWelcome: true }])
    setShowFaq(false)
  }

  const appendAssistant = (data) => {
    setConversationId(data.conversation_id)
    saveSession(activeCompanyId, { nickname, conversationId: data.conversation_id })
    setHumanMode(!!data.human_mode || !!data.need_human)
    if (!data.answer) return
    setMessages((prev) => [...prev, {
      id: data.message_id,
      role: 'assistant',
      content: data.answer,
      need_human: data.need_human,
      sources: data.sources,
    }])
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setShowFaq(false)
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
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
        <div className="bg-primary px-4 py-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-white text-sm">云</div>
          <div className="flex-1 min-w-0">
            <p className="text-white text-sm font-semibold">{shopName}</p>
            <p className="text-white/70 text-xs">
              {humanMode ? '人工客服处理中' : 'AI 智能客服 · 在线'} · {nickname}
            </p>
          </div>
          <button type="button" onClick={startNewConsult}
            className="text-xs text-white/90 border border-white/30 px-2 py-1 rounded-full hover:bg-white/10">
            新咨询
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
          {messages.map((msg, i) => {
            const meta = roleMeta(msg.role)
            return (
              <div key={msg.id ?? i} className={`flex ${meta.align === 'end' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${meta.bubble}`}>
                  {meta.label && !msg.isWelcome && (
                    <p className="text-xs opacity-50 mb-1">{meta.label}</p>
                  )}
                  <p className="whitespace-pre-wrap">{msg.content}</p>

                  {msg.need_human && humanMode && (
                    <div className="mt-2 px-2 py-1.5 bg-orange-50 border border-orange-200 rounded-lg text-xs text-orange-700">
                      已进入人工队列，坐席回复后会显示在这里
                    </div>
                  )}

                  {msg.sources?.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-gray-100">
                      <p className="text-xs text-gray-400 mb-1">参考来源</p>
                      {msg.sources.map((s, j) => (
                        <span key={j} className="inline-block text-xs bg-primary-light text-primary-dark px-1.5 py-0.5 rounded mr-1 mb-1">
                          {s.title}
                        </span>
                      ))}
                    </div>
                  )}

                  {msg.need_human && !humanMode && msg.role === 'assistant' && !msg.isWelcome && (
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
            )
          })}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white rounded-2xl px-4 py-3 shadow-sm text-sm text-gray-400">
                {humanMode ? '消息已送达坐席...' : '小云正在思考...'}
              </div>
            </div>
          )}
          <div ref={endRef} />
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

        <form onSubmit={handleSend} className="p-3 border-t border-gray-100 flex gap-2 bg-white items-center">
          <button type="button" onClick={() => setShowFaq((v) => !v)}
            className="shrink-0 text-xs px-2 py-2 border border-gray-200 text-gray-600 rounded-full hover:bg-gray-50"
            title="常见问题">
            常见
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
            className="flex-1 px-4 py-2.5 bg-gray-50 rounded-full text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button type="submit" disabled={loading}
            className="w-10 h-10 bg-primary text-white rounded-full flex items-center justify-center hover:bg-primary-dark disabled:opacity-60">
            ↑
          </button>
        </form>
      </div>
    </div>
  )
}
