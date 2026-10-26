import { useState, useEffect, useRef } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  listConversations, createConversation, getConversation, getCustomerProfile,
  sendMessage, closeConversation, triggerAiSuggest,
  acceptSuggestion, rejectSuggestion, acceptConversation,
  listConversationReviews, decideConversationReview,
} from '../api/conversations'
import { listQuickReplies, useQuickReply } from '../api/quickReplies'
import { createTicket } from '../api/tickets'
import { createDoc, listGaps, resolveGap } from '../api/knowledge'

function confidenceLevel(score) {
  if (score >= 0.7) return { label: '高', color: 'bg-green-100 text-green-700' }
  if (score >= 0.4) return { label: '中', color: 'bg-yellow-100 text-yellow-700' }
  return { label: '低', color: 'bg-red-100 text-red-600' }
}

function parseMeta(metaStr) {
  if (!metaStr) return {}
  try { return JSON.parse(metaStr) || {} } catch { return {} }
}

function formatMoment(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}

function ProfileStat({ label, value }) {
  return (
    <div className="rounded-lg bg-gray-50 px-2 py-2">
      <p className="text-base font-semibold text-gray-800 leading-none">{value ?? 0}</p>
      <p className="text-[10px] text-gray-400 mt-1">{label}</p>
    </div>
  )
}

function ProfileRow({ k, v }) {
  return (
    <div className="flex items-center justify-between text-[11px]">
      <span className="text-gray-400">{k}</span>
      <span className="text-gray-600">{v}</span>
    </div>
  )
}

function parseSources(sourcesStr) {
  if (!sourcesStr) return []
  try { return JSON.parse(sourcesStr) } catch { return [] }
}

function isSystemNotice(msg) {
  return msg.role === 'ai_suggestion' && msg.is_sent && (msg.confidence == null || msg.confidence < 0.6)
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

function ReviewCard({ review, onDecision, processing }) {
  const [note, setNote] = useState('')
  const waiting = review.status === 'waiting_review'
  const label = {
    pending_buyer: '待买家确认',
    waiting_review: '待坐席审核',
    approved: '已批准',
    rejected: '已拒绝',
    need_more_info: '待补材料',
  }[review.status] || review.status
  return (
    <div className="mx-auto max-w-[92%] border border-orange-200 bg-orange-50 rounded-xl p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold text-orange-800">{review.title}</p>
        <span className="text-xs px-2 py-0.5 rounded-full bg-white text-orange-700">{label}</span>
      </div>
      <p className="text-xs text-gray-600 mt-2">{review.detail}</p>
      <p className="text-xs text-red-600 mt-2">风险原因：{review.risk_reason || '涉及资金动作，需要人工审核'}</p>
      <div className="grid grid-cols-3 gap-2 mt-3 text-xs text-gray-600">
        <span>订单：{review.payload?.order_id || '未提供'}</span>
        <span>订单金额：¥{review.payload?.order_amount ?? '—'}</span>
        <span>建议退款：¥{review.payload?.refund_amount ?? '—'}</span>
      </div>
      {waiting && (
        <>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2}
            placeholder="审核备注；选择补材料时请写明缺什么"
            className="w-full mt-3 px-3 py-2 text-xs border border-orange-200 rounded-lg bg-white" />
          <div className="flex gap-2 mt-2">
            <button onClick={() => onDecision(review, 'approved', note)} disabled={processing}
              className="px-3 py-1.5 text-xs bg-green-600 text-white rounded-lg disabled:opacity-60">批准</button>
            <button onClick={() => onDecision(review, 'rejected', note)} disabled={processing}
              className="px-3 py-1.5 text-xs bg-red-500 text-white rounded-lg disabled:opacity-60">拒绝</button>
            <button onClick={() => onDecision(review, 'need_more_info', note)} disabled={processing || !note.trim()}
              className="px-3 py-1.5 text-xs border border-orange-300 text-orange-700 rounded-lg disabled:opacity-40">补材料</button>
          </div>
        </>
      )}
      {review.review_note && <p className="text-xs text-gray-500 mt-2">审核备注：{review.review_note}</p>}
    </div>
  )
}

const STATUS_FILTERS = [
  { value: '', label: '全部' },
  { value: 'waiting_human', label: '待人工' },
  { value: 'active', label: '进行中' },
  { value: 'closed', label: '已关闭' },
]

function formatRelativeTime(iso) {
  if (!iso) return ''
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins} 分钟前`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 7) return `${days} 天前`
  return new Date(iso).toLocaleDateString('zh-CN')
}

export default function Conversations() {
  const [searchParams] = useSearchParams()
  const [conversations, setConversations] = useState([])
  const [waitingCount, setWaitingCount] = useState(0)
  const [activeId, setActiveId] = useState(null)
  const [activeConv, setActiveConv] = useState(null)
  const [messages, setMessages] = useState([])
  const [reviews, setReviews] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(true)
  const [sending, setSending] = useState(false)
  const [processing, setProcessing] = useState(false)
  const [showOutbound, setShowOutbound] = useState(false)
  const [editSuggestion, setEditSuggestion] = useState(null)
  const [editContent, setEditContent] = useState('')
  const [outboundForm, setOutboundForm] = useState({
    customer_name: '',
    channel: 'web',
    first_message: '',
  })
  const [showQuickReplies, setShowQuickReplies] = useState(false)
  const [quickReplies, setQuickReplies] = useState([])
  const [statusFilter, setStatusFilter] = useState('')
  const [saveKb, setSaveKb] = useState(null)
  const [savingKb, setSavingKb] = useState(false)
  const [profile, setProfile] = useState(null)
  const [internalNote, setInternalNote] = useState(false)
  const [keyword, setKeyword] = useState('')
  const messagesEndRef = useRef(null)
  const messagesBoxRef = useRef(null)
  const atBottomRef = useRef(true)
  const activeIdRef = useRef(null)
  const prevWaitingRef = useRef(0)
  const openedFromUrl = useRef(false)

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

  const updateDocTitle = (count) => {
    document.title = count > 0 ? `(${count}) 待人工 - 小云智服` : '小云智服 - AI售后客服协同工作台'
  }

  const loadWaitingCount = async () => {
    try {
      const res = await listConversations('waiting_human')
      const count = res.data.length
      setWaitingCount(count)
      updateDocTitle(count)
      prevWaitingRef.current = count
    } catch {
      /* ignore */
    }
  }

  const loadList = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const res = await listConversations(statusFilter || undefined)
      setConversations(res.data)
      await loadWaitingCount()
    } finally {
      if (!silent) setLoading(false)
    }
  }

  const loadConversation = async (id, silent = false) => {
    const switching = !silent && id !== activeIdRef.current
    if (!silent) setActiveId(id)
    activeIdRef.current = id
    if (switching) {
      setInput('')
      setEditSuggestion(null)
      setEditContent('')
      setShowQuickReplies(false)
      setSaveKb(null)
      setInternalNote(false)
      setProfile(null)
      atBottomRef.current = true
    }
    const [res, reviewRes] = await Promise.all([
      getConversation(id),
      listConversationReviews(id),
    ])
    setActiveConv(res.data)
    setMessages(res.data.messages || [])
    setReviews(reviewRes.data || [])
    if (switching) {
      requestAnimationFrame(() => {
        const el = messagesBoxRef.current
        if (el) el.scrollTop = el.scrollHeight
      })
    }
    try {
      const p = await getCustomerProfile(id)
      setProfile(p.data)
    } catch {
      /* 客户信息卡失败不影响主流程 */
    }
  }

  const openSaveToKnowledge = (agentMsg) => {
    const idx = messages.findIndex((m) => m.id === agentMsg.id)
    let question = ''
    for (let i = idx - 1; i >= 0; i -= 1) {
      if (messages[i].role === 'customer') {
        question = messages[i].content
        break
      }
    }
    if (!question) {
      const lastCustomer = [...messages].reverse().find((m) => m.role === 'customer')
      question = lastCustomer?.content || ''
    }
    setSaveKb({
      question: question.trim(),
      answer: agentMsg.content.trim(),
      msgId: agentMsg.id,
    })
  }

  const handleSaveToKnowledge = async (e) => {
    e.preventDefault()
    if (!saveKb?.question?.trim() || !saveKb?.answer?.trim()) return
    setSavingKb(true)
    try {
      const question = saveKb.question.trim()
      const answer = saveKb.answer.trim()
      const gapsRes = await listGaps()
      const matched = (gapsRes.data || []).filter(
        (g) => ['pending', 'indexing_failed'].includes(g.status)
          && (g.question.trim() === question || g.question.includes(question) || question.includes(g.question.trim()))
      )
      let docId
      if (matched.length > 0) {
        const resolved = await resolveGap(matched[0].id, answer, true)
        docId = resolved.data.knowledge_doc_id
      } else {
        const created = await createDoc({
          title: question.slice(0, 100),
          content: `问：${question}\n\n答：${answer}`,
          category: '缺口补充',
        })
        docId = created.data.id
      }
      setSaveKb(null)
      alert(`已写入知识库（文档 #${docId}），下次同类问题可被检索`)
    } catch (err) {
      alert(err.response?.data?.detail || '写入知识库失败')
    } finally {
      setSavingKb(false)
    }
  }

  const refreshMessages = async () => {
    if (!activeIdRef.current) return
    await loadConversation(activeIdRef.current, true)
    loadList(true)
  }

  useEffect(() => { loadList() }, [statusFilter])

  useEffect(() => {
    if (openedFromUrl.current || loading) return
    const idParam = searchParams.get('id')
    if (!idParam) return
    const id = parseInt(idParam, 10)
    if (!Number.isNaN(id)) {
      openedFromUrl.current = true
      loadConversation(id)
    }
  }, [loading, searchParams])

  useEffect(() => {
    const el = messagesBoxRef.current
    if (!el || !atBottomRef.current) return
    el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const handleMessagesScroll = () => {
    const el = messagesBoxRef.current
    if (!el) return
    atBottomRef.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
  }

  useEffect(() => {
    const timer = setInterval(() => {
      loadList(true)
      if (activeIdRef.current) loadConversation(activeIdRef.current, true)
    }, 3000)
    return () => {
      clearInterval(timer)
      document.title = '小云智服 - AI售后客服协同工作台'
    }
  }, [statusFilter])

  const handleOutbound = async (e) => {
    e.preventDefault()
    if (!outboundForm.customer_name.trim() || !outboundForm.first_message.trim()) return
    setSending(true)
    try {
      const res = await createConversation({
        customer_name: outboundForm.customer_name.trim(),
        channel: outboundForm.channel,
      })
      const id = res.data.id
      await sendMessage(id, { content: outboundForm.first_message.trim(), role: 'agent' })
      setShowOutbound(false)
      setOutboundForm({ customer_name: '', channel: 'web', first_message: '' })
      await loadList()
      loadConversation(id)
    } catch (err) {
      alert(err.response?.data?.detail || '外联失败')
    } finally {
      setSending(false)
    }
  }

  const handleSend = async (e) => {
    e.preventDefault()
    if (!input.trim() || !activeId) return
    if (replyBlocked && !internalNote) return
    setSending(true)
    try {
      await sendMessage(activeId, { content: input, role: 'agent', is_internal: internalNote })
      setInput('')
      await refreshMessages()
    } finally {
      setSending(false)
    }
  }

  const handleAcceptHandoff = async () => {
    if (!activeId) return
    setProcessing(true)
    try {
      await acceptConversation(activeId)
      await refreshMessages()
    } catch (err) {
      alert(err.response?.data?.detail || '接入失败')
    } finally {
      setProcessing(false)
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

  const handleReviewDecision = async (review, decision, note) => {
    setProcessing(true)
    try {
      await decideConversationReview(activeId, review.id, decision, note)
      await refreshMessages()
    } catch (err) {
      alert(err.response?.data?.detail || '审核失败')
    } finally {
      setProcessing(false)
    }
  }

  const handleClose = async () => {
    if (!activeId) return
    if (!confirm('确认关闭该会话？')) return
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

  const chatMessages = messages.filter((m) => m.role !== 'ai_suggestion' || (m.is_sent && m.suggestion_status !== 'rejected'))
  const kw = keyword.trim().toLowerCase()
  const visibleConversations = kw
    ? conversations.filter((c) =>
        (c.customer_name || '').toLowerCase().includes(kw) ||
        (c.last_message || '').toLowerCase().includes(kw))
    : conversations
  const pendingSuggestions = messages.filter((m) => m.role === 'ai_suggestion' && (m.suggestion_status === 'pending' || !m.is_sent))
  const canReply = activeConv && activeConv.status !== 'closed'
  const hasCustomerMsg = messages.some((m) => m.role === 'customer')
  const hasWaitingReview = reviews.some((review) => review.status === 'waiting_review')
  const needsAccept = activeConv?.status === 'waiting_human' && !hasWaitingReview
  const replyBlocked = needsAccept || hasWaitingReview

  return (
    <div className="flex flex-col h-[calc(100vh-7rem)] gap-3">
      {waitingCount > 0 && (
        <div className="shrink-0 flex items-center justify-between px-4 py-2.5 bg-orange-50 border border-orange-200 rounded-xl">
          <p className="text-sm text-orange-700">
            有 <span className="font-semibold">{waitingCount}</span> 条会话待人工接入
          </p>
          <button
            type="button"
            onClick={() => setStatusFilter('waiting_human')}
            className="text-xs px-3 py-1 bg-orange-500 text-white rounded-lg hover:bg-orange-600"
          >
            查看待人工
          </button>
        </div>
      )}

      <div className="flex flex-1 min-h-0 bg-white rounded-xl shadow-sm overflow-hidden">
        <div className="w-72 border-r border-gray-100 flex flex-col flex-shrink-0">
          <div className="p-4 border-b border-gray-100">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-sm font-semibold text-gray-700">会话列表</h2>
              <button onClick={() => setShowOutbound(true)} className="text-xs bg-primary text-white px-2.5 py-1 rounded-lg hover:bg-primary-dark">
                外联客户
              </button>
            </div>
            <div className="flex flex-wrap gap-1">
              {STATUS_FILTERS.map((f) => (
                <button key={f.value} onClick={() => setStatusFilter(f.value)}
                  className={`px-2 py-0.5 text-xs rounded-full border ${
                    statusFilter === f.value ? 'bg-primary text-white border-primary' : 'border-gray-200 text-gray-500'
                  }`}>
                  {f.label}
                  {f.value === 'waiting_human' && waitingCount > 0 ? ` ${waitingCount}` : ''}
                </button>
              ))}
            </div>
            <input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="搜索客户名 / 消息内容"
              className="mt-2 w-full px-2.5 py-1.5 text-xs border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
            />
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <p className="text-center text-gray-400 text-xs p-4">加载中...</p>
            ) : visibleConversations.length === 0 ? (
              <p className="text-center text-gray-400 text-xs p-4">
                {kw ? '没有匹配的会话' : <>暂无会话<br /><span className="text-gray-300">买家可从 /chat 进线</span></>}
              </p>
            ) : (
              visibleConversations.map((c) => (
                <button
                  key={c.id}
                  onClick={() => loadConversation(c.id)}
                  className={`w-full text-left px-4 py-3 border-b border-gray-50 hover:bg-gray-50 transition-colors ${
                    activeId === c.id ? 'bg-primary-light' : ''
                  } ${c.status === 'waiting_human' ? 'border-l-4 border-l-orange-400' : ''}`}
                >
                  <div className="flex items-center justify-between">
                    <span className={`text-sm font-medium truncate ${c.unread_count > 0 ? 'text-gray-900' : 'text-gray-800'}`}>
                      {c.customer_name}
                      {c.unread_count > 0 && (
                        <span className="ml-1.5 inline-flex min-w-[1.1rem] h-4 px-1 rounded-full bg-red-500 text-white text-[10px] items-center justify-center align-middle">
                          {c.unread_count > 99 ? '99+' : c.unread_count}
                        </span>
                      )}
                    </span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {c.last_message_at && (
                        <span className="text-[10px] text-gray-300">{formatRelativeTime(c.last_message_at)}</span>
                      )}
                      <span className={`text-xs px-1.5 py-0.5 rounded-full ${statusClass(c.status)}`}>
                        {statusText(c.status)}
                      </span>
                    </div>
                  </div>
                  <p className={`text-xs mt-0.5 truncate ${c.unread_count > 0 ? 'text-gray-700 font-medium' : 'text-gray-400'}`}>
                    {c.last_message || '暂无消息'}
                  </p>
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
                  {needsAccept && (
                    <button onClick={handleAcceptHandoff} disabled={processing}
                      className="text-xs px-3 py-1 bg-orange-500 text-white rounded-lg hover:bg-orange-600 disabled:opacity-60">
                      接入
                    </button>
                  )}
                  {canReply && (
                    <button onClick={handleRegenerate} disabled={processing || !hasCustomerMsg}
                      className="text-xs text-primary hover:underline disabled:opacity-40">
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

              <div ref={messagesBoxRef} onScroll={handleMessagesScroll} className="flex-1 overflow-y-auto p-5 space-y-3">
                {chatMessages.length === 0 && pendingSuggestions.length === 0 && (
                  <p className="text-center text-gray-300 text-sm mt-8">
                    {activeConv.status === 'waiting_human'
                      ? '买家已转人工，请点击「接入」后回复'
                      : '暂无消息'}
                  </p>
                )}
                {chatMessages.map((msg) => (
                  msg.is_internal ? (
                    <div key={msg.id} className="flex justify-center">
                      <div className="max-w-[85%] text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2">
                        <span className="font-medium">内部备注 · </span>{msg.content}
                        <span className="opacity-50 ml-2">（买家不可见）</span>
                      </div>
                    </div>
                  ) : isSystemNotice(msg) ? (
                    <div key={msg.id} className="flex justify-center">
                      <div className="max-w-[85%] text-center text-xs text-gray-500 bg-gray-100 rounded-lg px-3 py-2">
                        <span className="opacity-70">系统 · </span>{msg.content}
                      </div>
                    </div>
                  ) : (
                    <div key={msg.id} className={`flex ${msg.role === 'agent' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[70%] rounded-xl px-4 py-2.5 ${roleColor[msg.role] || 'bg-gray-50'}`}>
                        <p className="text-xs font-medium mb-0.5 opacity-60">{roleLabel[msg.role] || msg.role}</p>
                        <p className="text-sm">{msg.content}</p>
                        {parseMeta(msg.meta).internal_note && (
                          <div className="mt-2 rounded-lg bg-amber-50 border border-amber-200 px-2 py-1.5">
                            <p className="text-[10px] font-medium text-amber-700 mb-0.5">内部信息 · 买家不可见</p>
                            <p className="text-[11px] text-amber-800 whitespace-pre-wrap">
                              {parseMeta(msg.meta).internal_note}
                            </p>
                          </div>
                        )}
                        {parseMeta(msg.meta).plan_steps?.length > 0 && (
                          <details className="mt-2 rounded-lg bg-white/70 border border-black/5 px-2 py-1.5">
                            <summary className="text-[11px] text-gray-500 cursor-pointer select-none">
                              AI 执行计划{parseMeta(msg.meta).intent_label ? ` · ${parseMeta(msg.meta).intent_label}` : ''}
                              （{parseMeta(msg.meta).plan_steps.length} 步）
                            </summary>
                            <ul className="mt-1 space-y-0.5">
                              {parseMeta(msg.meta).plan_steps.map((s, i) => (
                                <li key={i} className="text-[11px] text-gray-500">
                                  · {s.title}{s.detail ? `：${s.detail}` : ''}
                                  {s.demo ? '（演示数据）' : ''}
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                        {parseSources(msg.sources).length > 0 && (
                          <div className="mt-2 pt-2 border-t border-black/5">
                            {parseSources(msg.sources).map((s, i) => (
                              <span key={i} className="inline-block text-xs bg-white/70 text-gray-600 px-1.5 py-0.5 rounded mr-1 mb-1">
                                {s.title}
                              </span>
                            ))}
                          </div>
                        )}
                        <p className="text-xs opacity-40 mt-1">{new Date(msg.created_at).toLocaleTimeString('zh-CN')}</p>
                      </div>
                    </div>
                  )
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
                {reviews.map((review) => (
                  <ReviewCard key={review.id} review={review} onDecision={handleReviewDecision} processing={processing} />
                ))}
                <div ref={messagesEndRef} />
              </div>

              {canReply ? (
                <form onSubmit={handleSend} className="p-4 border-t border-gray-100 flex gap-2">
                  <button type="button" onClick={() => setInternalNote((v) => !v)}
                    className={`shrink-0 px-2.5 py-2 text-xs rounded-lg border ${
                      internalNote
                        ? 'bg-amber-50 border-amber-300 text-amber-700'
                        : 'border-gray-200 text-gray-500 hover:bg-gray-50'
                    }`}
                    title="内部备注：只在坐席端可见，买家看不到">
                    内部备注
                  </button>
                  <input
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    placeholder={
                      internalNote
                        ? '写内部备注（买家不可见），如：该客户已三次进线'
                        : hasWaitingReview ? '请先在审核卡中批准、拒绝或要求补充材料...' : (needsAccept ? '请先点击「接入」再回复...' : '回复买家（将同步到买家端）...')
                    }
                    disabled={replyBlocked && !internalNote}
                    className={`flex-1 px-4 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary disabled:bg-gray-50 ${
                      internalNote ? 'border-amber-200 bg-amber-50/40' : 'border-gray-200'
                    }`}
                  />
                  <button type="button" onClick={openQuickReplies}
                    className="px-3 py-2 text-xs border border-gray-200 rounded-lg text-gray-500 hover:bg-gray-50">
                    话术
                  </button>
                  <button type="submit" disabled={sending || (replyBlocked && !internalNote)}
                    className={`px-5 py-2 text-sm rounded-lg disabled:opacity-60 ${
                      internalNote
                        ? 'bg-amber-500 text-white hover:bg-amber-600'
                        : 'bg-primary text-white hover:bg-primary-dark'
                    }`}>
                    {internalNote ? '存备注' : '发送'}
                  </button>
                </form>
              ) : (
                <div className="p-4 border-t border-gray-100 text-center text-sm text-gray-400">会话已关闭</div>
              )}
            </>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-gray-300 text-sm gap-2">
              <p>选择左侧会话，或打开买家端开始进线</p>
              <a href="/chat?new=1" target="_blank" rel="noreferrer" className="text-primary text-xs hover:underline">打开买家端 /chat ↗</a>
            </div>
          )}
        </div>

        {activeConv && profile && (
          <aside className="w-64 border-l border-gray-100 flex flex-col shrink-0 overflow-y-auto">
            <div className="p-4 border-b border-gray-100">
              <p className="text-xs font-semibold text-gray-500 mb-2">客户信息</p>
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-full bg-primary/10 text-primary flex items-center justify-center text-sm shrink-0">
                  {(profile.customer_name || '客').slice(0, 1)}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-gray-800 truncate">{profile.customer_name}</p>
                  <p className="text-[11px] text-gray-400">{profile.channel} · {statusText(profile.status)}</p>
                </div>
              </div>
            </div>

            <div className="p-4 grid grid-cols-2 gap-2 border-b border-gray-100">
              <ProfileStat label="进线次数" value={profile.total_conversations} />
              <ProfileStat label="本会话消息" value={profile.total_messages} />
              <ProfileStat label="未结工单" value={profile.open_tickets} />
              <ProfileStat label="关联订单" value={profile.orders?.length || 0} />
            </div>

            <div className="p-4 border-b border-gray-100 space-y-1.5">
              <ProfileRow k="首次进线" v={formatMoment(profile.first_contact_at)} />
              <ProfileRow k="最近活跃" v={formatMoment(profile.last_active_at)} />
            </div>

            <div className="p-4">
              <p className="text-xs font-semibold text-gray-500 mb-2">关联订单</p>
              {profile.orders?.length ? profile.orders.map((o) => (
                <div key={o.order_id} className="mb-2 p-2 rounded-lg border border-gray-100 bg-gray-50">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-medium text-gray-700">{o.order_id}</span>
                    <span className="text-[10px] text-gray-500 shrink-0">{o.status}</span>
                  </div>
                  <p className="text-[11px] text-gray-500 mt-0.5 truncate">{o.product}</p>
                  <p className="text-[10px] text-gray-400">
                    ¥{o.amount} · 购后 {o.days_since_purchase} 天 · {o.express}
                  </p>
                </div>
              )) : (
                <p className="text-[11px] text-gray-300">无匹配的演示订单</p>
              )}
            </div>
          </aside>
        )}
      </div>

      {showOutbound && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-base font-semibold text-gray-800 mb-1">外联客户</h3>
            <p className="text-xs text-gray-400 mb-4">主动联系客户：创建会话并立即发送首条坐席消息</p>
            <form onSubmit={handleOutbound} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">客户昵称</label>
                <input required value={outboundForm.customer_name}
                  onChange={(e) => setOutboundForm({ ...outboundForm, customer_name: e.target.value })}
                  placeholder="如：张女士"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">渠道</label>
                <select value={outboundForm.channel}
                  onChange={(e) => setOutboundForm({ ...outboundForm, channel: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary">
                  <option value="web">网页</option>
                  <option value="wechat">微信</option>
                  <option value="phone">电话</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">首条消息</label>
                <textarea required rows={3} value={outboundForm.first_message}
                  onChange={(e) => setOutboundForm({ ...outboundForm, first_message: e.target.value })}
                  placeholder="如：您好，关于您的换货申请我想跟您确认一下…"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none" />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowOutbound(false)} className="px-4 py-2 text-sm text-gray-500">取消</button>
                <button type="submit" disabled={sending} className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-60">
                  创建并发送
                </button>
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

      {saveKb && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
            <h3 className="text-base font-semibold text-gray-800 mb-1">写入知识库</h3>
            <p className="text-xs text-gray-400 mb-4">用本轮坐席回答沉淀标准问答，下次同类问题可被 AI 检索</p>
            <form onSubmit={handleSaveToKnowledge} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">客户问题</label>
                <textarea
                  required
                  rows={2}
                  value={saveKb.question}
                  onChange={(e) => setSaveKb({ ...saveKb, question: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">标准答案（已带入你刚发的回复，可微调）</label>
                <textarea
                  required
                  rows={5}
                  value={saveKb.answer}
                  onChange={(e) => setSaveKb({ ...saveKb, answer: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none"
                />
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setSaveKb(null)} className="px-4 py-2 text-sm text-gray-500">取消</button>
                <button type="submit" disabled={savingKb} className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-60">
                  {savingKb ? '写入中...' : '确认写入并索引'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

    </div>
  )
}
