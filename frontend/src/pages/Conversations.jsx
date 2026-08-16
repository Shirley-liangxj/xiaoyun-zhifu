import { useState, useEffect, useRef } from 'react'
import {
  listConversations, createConversation, getConversation,
  sendMessage, closeConversation, triggerAiSuggest,
  acceptSuggestion, rejectSuggestion,
} from '../api/conversations'

/** 置信度等级与颜色 */
function confidenceLevel(score) {
  if (score >= 0.7) return { label: '高', color: 'bg-green-100 text-green-700' }
  if (score >= 0.4) return { label: '中', color: 'bg-yellow-100 text-yellow-700' }
  return { label: '低', color: 'bg-red-100 text-red-600' }
}

/** 解析来源 JSON */
function parseSources(sourcesStr) {
  if (!sourcesStr) return []
  try { return JSON.parse(sourcesStr) } catch { return [] }
}

/** AI 建议卡片组件 */
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

      {/* 来源溯源 */}
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

      {/* 操作按钮 */}
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
  const messagesEndRef = useRef(null)

  const loadList = async () => {
    setLoading(true)
    try {
      const res = await listConversations()
      setConversations(res.data)
    } finally {
      setLoading(false)
    }
  }

  const loadConversation = async (id) => {
    setActiveId(id)
    const res = await getConversation(id)
    setActiveConv(res.data)
    setMessages(res.data.messages || [])
  }

  const refreshMessages = async () => {
    if (!activeId) return
    const res = await getConversation(activeId)
    setMessages(res.data.messages || [])
    loadList()
  }

  useEffect(() => { loadList() }, [])
  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

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

  const roleLabel = { customer: '客户', agent: '坐席' }
  const roleColor = {
    customer: 'bg-blue-50 text-blue-800',
    agent: 'bg-primary-light text-primary-dark',
  }

  // 分离普通消息和待处理 AI 建议
  const chatMessages = messages.filter((m) => m.role !== 'ai_suggestion' || m.is_sent)
  const pendingSuggestions = messages.filter((m) => m.role === 'ai_suggestion' && !m.is_sent)

  return (
    <div className="flex h-[calc(100vh-7rem)] bg-white rounded-xl shadow-sm overflow-hidden">
      {/* 左侧会话列表 */}
      <div className="w-72 border-r border-gray-100 flex flex-col flex-shrink-0">
        <div className="p-4 border-b border-gray-100 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700">会话列表</h2>
          <button onClick={() => setShowNew(true)} className="text-xs bg-primary text-white px-2.5 py-1 rounded-lg hover:bg-primary-dark">
            + 新建
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <p className="text-center text-gray-400 text-xs p-4">加载中...</p>
          ) : conversations.length === 0 ? (
            <p className="text-center text-gray-400 text-xs p-4">暂无会话</p>
          ) : (
            conversations.map((c) => (
              <button
                key={c.id}
                onClick={() => loadConversation(c.id)}
                className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors ${activeId === c.id ? 'bg-primary-light' : ''}`}
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-gray-800">{c.customer_name}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded-full ${c.status === 'active' ? 'bg-green-100 text-green-600' : 'bg-gray-100 text-gray-400'}`}>
                    {c.status === 'active' ? '进行中' : '已关闭'}
                  </span>
                </div>
                <p className="text-xs text-gray-400 mt-0.5 truncate">{c.last_message || '暂无消息'}</p>
                <p className="text-xs text-gray-300 mt-0.5">{c.message_count} 条消息 · {c.channel}</p>
              </button>
            ))
          )}
        </div>
      </div>

      {/* 右侧聊天区 */}
      <div className="flex-1 flex flex-col min-w-0">
        {activeConv ? (
          <>
            <div className="px-5 py-3 border-b border-gray-100 flex items-center justify-between">
              <div>
                <span className="text-sm font-semibold text-gray-800">{activeConv.customer_name}</span>
                <span className="text-xs text-gray-400 ml-2">{activeConv.channel}</span>
              </div>
              <div className="flex items-center gap-3">
                {activeConv.status === 'active' && (
                  <button onClick={handleRegenerate} disabled={processing}
                    className="text-xs text-primary hover:underline disabled:opacity-60">
                    重新生成建议
                  </button>
                )}
                {activeConv.status === 'active' && (
                  <button onClick={handleClose} className="text-xs text-red-500 hover:underline">关闭会话</button>
                )}
              </div>
            </div>

            <div className="flex-1 overflow-y-auto p-5 space-y-3">
              {chatMessages.length === 0 && pendingSuggestions.length === 0 && (
                <p className="text-center text-gray-300 text-sm mt-8">暂无消息，发送客户消息后将自动生成 AI 建议</p>
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

              {/* 待处理的 AI 建议 */}
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

            {activeConv.status === 'active' ? (
              <form onSubmit={handleSend} className="p-4 border-t border-gray-100 flex gap-2">
                <input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="输入回复内容..."
                  className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                />
                <button type="button" onClick={handleSimulateCustomer} disabled={sending}
                  className="px-3 py-2 text-xs border border-gray-200 rounded-lg text-gray-500 hover:bg-gray-50 disabled:opacity-60">
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
          <div className="flex-1 flex items-center justify-center text-gray-300 text-sm">
            选择或新建一个会话开始
          </div>
        )}
      </div>

      {/* 新建会话弹窗 */}
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

      {/* 编辑建议弹窗 */}
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
