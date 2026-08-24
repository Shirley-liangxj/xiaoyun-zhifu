import { useState, useEffect, useRef } from 'react'
import { getPublicConfig, getPublicConversation, publicChat, transferToHuman } from '../api/public'

function confidenceLabel(c) {
  if (c >= 0.7) return { text: '高置信', color: 'bg-green-100 text-green-700' }
  if (c >= 0.4) return { text: '中置信', color: 'bg-yellow-100 text-yellow-700' }
  return { text: '低置信', color: 'bg-red-100 text-red-600' }
}

function roleMeta(role) {
  if (role === 'user') return { align: 'end', bubble: 'bg-primary text-white rounded-br-md', label: '' }
  if (role === 'agent') return { align: 'start', bubble: 'bg-emerald-50 text-emerald-900 shadow-sm rounded-bl-md', label: '人工客服' }
  return { align: 'start', bubble: 'bg-white text-gray-800 shadow-sm rounded-bl-md', label: 'AI 小云' }
}

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const [humanMode, setHumanMode] = useState(false)
  const [welcome, setWelcome] = useState('您好！我是云裳服饰智能客服小云，有什么可以帮您的？')
  const [shopName, setShopName] = useState('云裳服饰客服')
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.6)
  const endRef = useRef(null)

  useEffect(() => {
    getPublicConfig()
      .then((res) => {
        if (res.data.welcome_message) setWelcome(res.data.welcome_message)
        if (res.data.company_name) setShopName(res.data.company_name + '客服')
        if (res.data.confidence_threshold) setConfidenceThreshold(res.data.confidence_threshold)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    setMessages([{ role: 'assistant', content: welcome, isWelcome: true }])
  }, [welcome])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  useEffect(() => {
    if (!conversationId) return undefined
    const timer = setInterval(async () => {
      try {
        const res = await getPublicConversation(conversationId)
        const data = res.data
        setHumanMode(!!data.human_mode)
        const remote = (data.messages || []).map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          confidence: m.confidence,
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
        /* ignore poll errors */
      }
    }, 2500)
    return () => clearInterval(timer)
  }, [conversationId])

  const appendAssistant = (data) => {
    setConversationId(data.conversation_id)
    setHumanMode(!!data.human_mode || !!data.need_human)
    if (!data.answer) return
    setMessages((prev) => [...prev, {
      id: data.message_id,
      role: 'assistant',
      content: data.answer,
      confidence: data.confidence,
      need_human: data.need_human,
      sources: data.sources,
    }])
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)
    try {
      const res = await publicChat(userMsg, conversationId)
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
    try {
      const res = await transferToHuman(conversationId)
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

  const shouldShowTransferBtn = (msg) => {
    if (humanMode || msg.isWelcome || msg.role !== 'assistant') return false
    if (msg.need_human) return true
    if (msg.confidence != null && msg.confidence < confidenceThreshold) return true
    return false
  }

  const quickQuestions = [
    '我买的衣服尺码不合适能换货吗？',
    '退货需要自己付运费吗？',
    '退款多久能到账？',
    '发什么快递？',
  ]

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
      <div className="w-full max-w-[390px] h-[720px] bg-white rounded-3xl shadow-2xl flex flex-col overflow-hidden border border-gray-200">
        <div className="bg-primary px-4 py-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-white text-sm">云</div>
          <div className="flex-1">
            <p className="text-white text-sm font-semibold">{shopName}</p>
            <p className="text-white/70 text-xs">{humanMode ? '人工客服处理中' : 'AI 智能客服 · 在线'}</p>
          </div>
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

                  {msg.confidence !== undefined && msg.confidence !== null && !msg.isWelcome && msg.role !== 'agent' && (
                    <div className="mt-1.5 flex items-center gap-1">
                      <span className={`text-xs px-1.5 py-0.5 rounded-full ${confidenceLabel(msg.confidence).color}`}>
                        {confidenceLabel(msg.confidence).text} {(msg.confidence * 100).toFixed(0)}%
                      </span>
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

                  {shouldShowTransferBtn(msg) && (
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

        {messages.filter((m) => !m.isWelcome).length === 0 && (
          <div className="px-4 py-2 flex gap-1.5 flex-wrap border-t border-gray-100">
            {quickQuestions.map((q) => (
              <button key={q} onClick={() => setInput(q)}
                className="text-xs px-2.5 py-1 bg-white border border-gray-200 rounded-full text-gray-600 hover:border-primary hover:text-primary">
                {q}
              </button>
            ))}
          </div>
        )}

        <form onSubmit={handleSend} className="p-3 border-t border-gray-100 flex gap-2 bg-white items-center">
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
