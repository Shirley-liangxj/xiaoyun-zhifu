import { useState, useEffect, useRef } from 'react'
import { publicChat } from '../api/public'

function confidenceLabel(c) {
  if (c >= 0.7) return { text: '高置信', color: 'bg-green-100 text-green-700' }
  if (c >= 0.4) return { text: '中置信', color: 'bg-yellow-100 text-yellow-700' }
  return { text: '低置信', color: 'bg-red-100 text-red-600' }
}

export default function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [conversationId, setConversationId] = useState(null)
  const endRef = useRef(null)

  useEffect(() => {
    setMessages([{
      role: 'assistant',
      content: '您好！我是云裳服饰智能客服小云，有什么可以帮您的？',
      isWelcome: true,
    }])
  }, [])

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return
    const userMsg = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMsg }])
    setLoading(true)
    try {
      const res = await publicChat(userMsg, conversationId)
      const data = res.data
      setConversationId(data.conversation_id)
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: data.answer,
        confidence: data.confidence,
        need_human: data.need_human,
        sources: data.sources,
      }])
    } catch (err) {
      setMessages((prev) => [...prev, {
        role: 'assistant',
        content: '抱歉，服务暂时不可用，请稍后再试。',
        error: true,
      }])
    } finally {
      setLoading(false)
    }
  }

  const quickQuestions = [
    '我买的衣服尺码不合适能换货吗？',
    '退货需要自己付运费吗？',
    '退款多久能到账？',
    '发什么快递？',
  ]

  return (
    <div className="min-h-screen bg-gray-100 flex items-center justify-center p-4">
      {/* 手机框 */}
      <div className="w-full max-w-[390px] h-[720px] bg-white rounded-3xl shadow-2xl flex flex-col overflow-hidden border border-gray-200">
        {/* 顶栏 */}
        <div className="bg-primary px-4 py-3 flex items-center gap-3">
          <div className="w-9 h-9 rounded-full bg-white/20 flex items-center justify-center text-white text-sm">云</div>
          <div>
            <p className="text-white text-sm font-semibold">云裳服饰客服</p>
            <p className="text-white/70 text-xs">AI 智能客服 · 在线</p>
          </div>
        </div>

        {/* 消息区 */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gray-50">
          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm ${
                msg.role === 'user'
                  ? 'bg-primary text-white rounded-br-md'
                  : 'bg-white text-gray-800 shadow-sm rounded-bl-md'
              }`}>
                <p className="whitespace-pre-wrap">{msg.content}</p>

                {msg.need_human && (
                  <div className="mt-2 px-2 py-1.5 bg-orange-50 border border-orange-200 rounded-lg text-xs text-orange-700">
                    已为您转接人工客服，请稍候...
                  </div>
                )}

                {msg.confidence !== undefined && !msg.isWelcome && (
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
              </div>
            </div>
          ))}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white rounded-2xl px-4 py-3 shadow-sm text-sm text-gray-400">
                小云正在思考...
              </div>
            </div>
          )}
          <div ref={endRef} />
        </div>

        {/* 快捷提问 */}
        {messages.length <= 1 && (
          <div className="px-4 py-2 flex gap-1.5 flex-wrap border-t border-gray-100">
            {quickQuestions.map((q) => (
              <button key={q} onClick={() => setInput(q)}
                className="text-xs px-2.5 py-1 bg-white border border-gray-200 rounded-full text-gray-600 hover:border-primary hover:text-primary">
                {q}
              </button>
            ))}
          </div>
        )}

        {/* 输入区 */}
        <form onSubmit={handleSend} className="p-3 border-t border-gray-100 flex gap-2 bg-white">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="输入您的问题..."
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
