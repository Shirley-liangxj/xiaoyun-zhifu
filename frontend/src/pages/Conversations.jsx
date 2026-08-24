import { useState, useEffect, useRef } from 'react'
import {
  listConversations, createConversation, getConversation,
  sendMessage, closeConversation, triggerAiSuggest,
  acceptSuggestion, rejectSuggestion,
} from '../api/conversations'
import { listQuickReplies, useQuickReply } from '../api/quickReplies'
import { createTicket } from '../api/tickets'

function confidenceLevel(score) {
  if (score >= 0.7) return { label: '高', color: 'bg-green-100 text-green-700' }
  if (score >= 0.4) return { label: '中', color: 'bg-yellow-100 text-yellow-700' }
  return { label: '低', color: 'bg-red-100 text-red-600' }
}

function parseSources(sourcesStr) {
  if (!sourcesStr) return []
  try { return JSON.parse(sourcesStr) } catch { return [] }
}

function SuggestionCard({ msg, onAccept, onEdit, onReject, processing }) {
  const conf = confidenceLevel(msg.confidence || 0)
  const sources = parseSources(msg.sources)

  return (
    <div className="mx-auto max-w-[85%] border-2 border-dashed border-yellow-300 bg-yellow-50 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-yellow-700">AI 回复建议</span>
          <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${conf.color}`}>
            置信度 {conf.label} {(msg.confidence * 100).toFixed(0)}%
          </span>
        </div>
      </div>
      <p className="text-sm text-gray-800 mb-3">{msg.content}</p>
      {sources.length > 0 && (
        <div className="mb-3 p-2 bg-white/60 rounded-lg">
          <p className="text-xs text-gray-400 mb-1">参考来源</p>
          {sources.map((s, i) => (
            <div key={i} className="text-xs text-gray-500 flex items-center gap-1">
              <span className="text-primary">[{i + 1}]</span>
              <span>{s.title}</span>
              <span className="text-gray-300">({(s.score * 100).toFixed(0)}%)</span>
            </div>
          ))}
        </div>
      )}
      <div className="flex gap-2">
        <button onClick={() => onAccept(msg)} disabled={processing}
          className="px-3 py-1.5 text-xs bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-60">
          采纳发送
        </button>
        <button onClick={() => onEdit(msg)} disabled={processing}
          className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg text-gray-600 hover:bg-white disabled:opacity-60">
          编辑后发送
        </button>
        <button onClick={() => onReject(msg.id)} disabled={processing}
          className="px-3 py-1.5 text-xs text-gray-400 hover:text-red-500 disabled:opacity-60">
          忽略
        </button>
      </div>
    </div>
  )
}

const STATUS_FILTERS = [
  { value: '', label: '全部' },
  { value: 'waiting_human', label: '待人工' },
  { value: 'active', label: '进行中' },
  { value: 'closed', label: '已关闭' },
]

export default function Conversations() {
  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [activeConv, setActiveConv] = useState(null)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [showNew, setShowNew] = useState(false)
  const [editSuggestion, setEditSuggestion] = useState(null)
  const [editContent, setEditContent] = useState('')
  const [newForm, setNewForm] = useState({ customer_name: '', channel: 'web' })
  const [showQuickReplies, setShowQuickReplies] = useState(false)
  const [quickReplies, setQuickReplies] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const messagesEndRef = useRef(null)
  const activeIdRef = useRef(null)

  const statusText = (s) => {
    if (s === 'waiting_human') return '待人工'
    if (s === 'active') return '进行中'
    return '已关闭'
  }
  const statusClass = (s) => {
    if (s === 'waiting_human') return 'bg-orange-100 text-orange-600'
    if (s === 'active') return 'bg-green-100 text-green-600'
    return 'bg-gray-100 text-gray-400'
  }

  const loadList = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const res = await listConversations(statusFilter || undefined)
      setConversations(res.data)
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const loadConversation = async (id, silent = false) => {
    if (!silent) setActiveId(id)
    activeIdRef.current = id
    const res = await getConversation(id)
    setActiveConv(res.data)
    setMessages(res.data.messages || [])
  }

  const refreshMessages = async () => {
    if (!activeIdRef.current) return
    await loadConversation(activeIdRef.current, true)
    loadList(true)
  }

  useEffect(() => { loadList() }, [statusFilter])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  useEffect(() => {
    const timer = setInterval(() => {
      loadList(true)
      if (activeIdRef.current) loadConversation(activeIdRef.current, true)
    }, 3000)
    return () => clearInterval(timer)
  }, [statusFilter])

  const handleCreate = async (e) => {
    e.preventDefault()
    const res = await createConversation(newForm)
    setShowNew(false)
    setNewForm({ customer_name: '', channel: 'web' })
    await loadList()
    loadConversation(res.data.id)
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || !activeId) return
    setSending(true)
    try {
      await sendMessage(activeId, { content: input, role: 'agent' })
      setInput('')
      await refreshMessages()
    } finally {
      setSending(false)
    }
  }

  const handleSimulateCustomer = async () => {
    if (!input.trim() || !activeId) return
    setSending(true)
    try {
      await sendMessage(activeId, { content: input, role: 'customer' })
      setInput('')
      await refreshMessages()
    } finally {
      setSending(false)
    }
  }

  const handleRegenerate = async () => {
    if (!activeId) return
    setProcessing(true)
    try {
      await triggerAiSuggest(activeId)
      await refreshMessages()
    } catch (err) {
      alert(err.response?.data?.detail || '生成失败')
    } finally {
      setProcessing(false)
    }
  }

  const handleAccept = async (msg) => {
    setProcessing(true)
    try {
      await acceptSuggestion(activeId, msg.id)
      await refreshMessages()
    } finally {
      setProcessing(false)
    }
  }

  const handleEdit = (msg) => {
    setEditSuggestion(msg)
    setEditContent(msg.content)
  }

  const handleEditSubmit = async (e) => {
    e.preventDefault()
    if (!editContent.trim()) return
    setProcessing(true)
    try {
      await acceptSuggestion(activeId, editSuggestion.id, editContent)
      setEditSuggestion(null)
      await refreshMessages()
    } finally {
      setProcessing(false)
    }
  }

  const handleReject = async (suggestionId) => {
    setProcessing(true)
    try {
      await rejectSuggestion(activeId, suggestionId)
      await refreshMessages()
    } finally {
      setProcessing(false)
    }
  }

  const handleClose = async () => {
    if (!activeId) return
    await closeConversation(activeId)
    loadList()
    loadConversation(activeId)
  }

  const handleCreateTicket = async () => {
    if (!activeConv) return
    const lastCustomer = [...messages].reverse().find((m) => m.role === 'customer')
    const title = `${activeConv.customer_name} 售后问题`
    const description = lastCustomer?.content || '来自会话转工单'
    try {
      await createTicket({
        title,
        description,
        priority: activeConv.status === 'waiting_human' ? 'high' : 'normal',
        conversation_id: activeConv.id,
      })
      alert('工单已创建，可在工单中心查看')
    } catch (err) {
      alert(err.response?.data?.detail || '创建工单失败')
    }
  }

  const openQuickReplies = async () => {
    const res = await listQuickReplies()
    setQuickReplies(res.data)
    setShowQuickReplies(true)
  }

  const insertQuickReply = async (reply) => {
    setInput(reply.content)
    await useQuickReply(reply.id)
    setShowQuickReplies(false)
  }

  const roleLabel = { customer: '客户', agent: '坐席', ai_suggestion: 'AI 客服' }
  const roleColor = {
    customer: 'bg-blue-50 text-blue-800',
    agent: 'bg-primary-light text-primary-dark',
    ai_suggestion: 'bg-purple-50 text-purple-800',
  }

  const chatMessages = messages.filter((m) => m.role !== 'ai_suggestion' || m.is_sent)
  const pendingSuggestions = messages.filter((m) => m.role === 'ai_suggestion' && !m.is_sent)
  const canReply = activeConv && activeConv.status !== 'closed'

  return (
    <div className="flex h-[calc(100vh-7rem)] bg-white rounded-xl shadow-sm overflow-hidden">
      <div className="w-72 border-r border-gray-100 flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-gray-100">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">会话列表</h2>
            <button onClick={() => setShowNew(true)} className="text-xs bg-primary text-white px-2.5 py-1 rounded-lg hover:bg-primary-dark">
              + 新建
            </button>
          </div>
          <div className="flex flex-wrap gap-1">
            {STATUS_FILTERS.map((f) => (
              <button key={f.value} onClick={() => setStatusFilter(f.value)}
                className={`px-2 py-0.5 text-xs rounded-full border ${
                  statusFilter === f.value ? 'bg-primary text-white border-primary' : 'border-gray-200 text-gray-500'
                }`}>
                {f.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <p className="text-center text-gray-400 text-xs p-4">加载中...</p>
          ) : conversations.length === 0 ? (
            <p className="text-center text-gray-400 text-xs p-4">暂无会话<br /><span className="text-gray-300">买家可从 /chat 进线</span></p>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => loadConversation(c.id)}
                className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors ${activeId === c.id ? 'bg-primary-light' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-800">{c.customer_name}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusClass(c.status)}`}>
                    {statusText(c.status)}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5 truncate">{c.last_message || '暂无消息'}</p>
                <p className="text-xs text-gray-300 mt-0.5">{c.message_count} 条消息 · {c.channel}</p>
              </button>
            ))
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col min-w-0">
        {activeConv ? (
          <>
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-gray-800">{activeConv.customer_name}</span>
                <span className="text-xs text-gray-400 ml-2">{activeConv.channel}</span>
                {activeConv.status === 'waiting_human' && (
                  <span className="ml-2 text-xs px-2 py-0.5 bg-orange-100 text-orange-600 rounded-full">待人工接入</span>
                )}
              </div>
              <div className="flex items-center gap-3">
                {canReply && (
                  <button onClick={handleRegenerate} disabled={processing}
                    className="text-xs text-primary hover:underline disabled:opacity-60">
                    重新生成建议
                  </button>
                )}
                {canReply && (
                  <button onClick={handleCreateTicket} className="text-xs text-orange-600 hover:underline">
                    转工单
                  </button>
                )}
                {canReply && (
                  <button onClick={handleClose} className="text-xs text-red-500 hover:underline">关闭会话</button>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {chatMessages.length === 0 && pendingSuggestions.length === 0 && (
                <p className="text-center text-gray-300 text-sm mt-8">
                  {activeConv.status === 'waiting_human'
                    ? '买家已转人工，请查看 AI 建议并回复'
                    : '暂无消息，买家从 /chat 进线后会自动出现'}
                </p>
              )}
              {chatMessages.map((msg) => (
                <div key={msg.id} className={`flex ${msg.role === 'agent' ? 'justify-end' : 'justify-start'}`}>
                  <div className={`max-w-[70%] rounded-xl px-4 py-2.5 ${roleColor[msg.role] || 'bg-gray-50'}`}>
                    <p className="text-xs font-medium mb-0.5 opacity-60">{roleLabel[msg.role] || msg.role}</p>
                    <p className="text-sm">{msg.content}</p>
                    <p className="text-xs opacity-40 mt-1">{new Date(msg.created_at).toLocaleTimeString('zh-CN')}</p>
                  </div>
                </div>
              ))}
              {pendingSuggestions.map((msg) => (
                <SuggestionCard
                  key={msg.id}
                  msg={msg}
                  onAccept={handleAccept}
                  onEdit={handleEdit}
                  onReject={handleReject}
                  processing={processing}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>

            {canReply ? (
              <form onSubmit={handleSend} className="p-4 border-t border-gray-100 flex gap-2">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder={activeConv.status === 'waiting_human' ? '回复买家（将同步到买家端）...' : '输入回复内容...'}
                  className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <button type="button" onClick={openQuickReplies}
                  className="px-3 py-2 text-xs border border-gray-200 rounded-lg text-gray-500 hover:bg-gray-50">
                  话术
                </button>
                <button type="button" onClick={handleSimulateCustomer} disabled={sending}
                  className="px-3 py-2 text-xs border border-gray-200 rounded-lg text-gray-400 hover:bg-gray-50 disabled:opacity-60"
                  title="仅演示用">
                  模拟客户
                </button>
                <button type="submit" disabled={sending}
                  className="px-5 py-2 bg-primary text-white text-sm rounded-lg hover:bg-primary-dark disabled:opacity-60">
                  发送
                </button>
              </form>
            ) : (
              <div className="p-4 border-t border-gray-100 text-center text-sm text-gray-400">会话已关闭</div>
            )}
          </>
        ) : (
          <div className="flex-1 flex flex-col items-center justify-center text-gray-300 text-sm gap-2">
            <p>选择左侧会话，或打开买家端开始演示</p>
            <a href="/chat" target="_blank" rel="noreferrer" className="text-primary text-xs hover:underline">打开买家端 /chat ↗</a>
          </div>
        )}
      </div>

      {showNew && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-sm p-6">
            <h3 className="text-base font-semibold text-gray-800 mb-4">新建会话</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">客户昵称</label>
                <input required value={newForm.customer_name} onChange={(e) => setNewForm({ ...newForm, customer_name: e.target.value })}
                  placeholder="如：张女士"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">渠道</label>
                <select value={newForm.channel} onChange={(e) => setNewForm({ ...newForm, channel: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary">
                  <option value="web">网页</option>
                  <option value="wechat">微信</option>
                  <option value="phone">电话</option>
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowNew(false)} className="px-4 py-2 text-sm text-gray-500">取消</button>
                <button type="submit" className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark">创建</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showQuickReplies && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 max-h-[70vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-gray-800">选择话术</h3>
              <button onClick={() => setShowQuickReplies(false)} className="text-gray-400 text-sm">关闭</button>
            </div>
            <div className="space-y-2">
              {quickReplies.map((r) => (
                <button key={r.id} onClick={() => insertQuickReply(r)}
                  className="w-full text-left p-3 border border-gray-100 rounded-lg hover:bg-primary-light hover:border-primary transition-colors">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs px-1.5 py-0.5 bg-gray-100 rounded">{r.category}</span>
                    <span className="text-sm font-medium text-gray-700">{r.title}</span>
                  </div>
                  <p className="text-xs text-gray-500 line-clamp-2">{r.content}</p>
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {editSuggestion && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
            <h3 className="text-base font-semibold text-gray-800 mb-4">编辑后发送</h3>
            <form onSubmit={handleEditSubmit} className="space-y-4">
              <textarea
                rows={6}
                value={editContent}
                onChange={(e) => setEditContent(e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
              />
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setEditSuggestion(null)} className="px-4 py-2 text-sm text-gray-500">取消</button>
                <button type="submit" disabled={processing} className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-60">
                  确认发送
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
