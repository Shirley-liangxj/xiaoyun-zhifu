import { useState, useEffect } from 'react'
import { listTickets, createTicket, updateTicket, deleteTicket } from '../api/tickets'

const STATUS_MAP = {
  open: { label: '待处理', color: 'bg-orange-100 text-orange-600' },
  in_progress: { label: '处理中', color: 'bg-blue-100 text-blue-600' },
  resolved: { label: '已解决', color: 'bg-green-100 text-green-600' },
  closed: { label: '已关闭', color: 'bg-gray-100 text-gray-500' },
}

const PRIORITY_MAP = {
  low: { label: '低', color: 'text-gray-400' },
  normal: { label: '普通', color: 'text-gray-600' },
  high: { label: '高', color: 'text-orange-500' },
  urgent: { label: '紧急', color: 'text-red-500 font-semibold' },
}

const STATUS_OPTIONS = ['open', 'in_progress', 'resolved', 'closed']
const PRIORITY_OPTIONS = ['low', 'normal', 'high', 'urgent']

export default function Tickets() {
  const [tickets, setTickets] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')
  const [priorityFilter, setPriorityFilter] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [detail, setDetail] = useState(null)
  const [form, setForm] = useState({ title: '', description: '', priority: 'normal' })

  const loadTickets = async () => {
    setLoading(true)
    try {
      const params = {}
      if (statusFilter) params.status_filter = statusFilter
      if (priorityFilter) params.priority_filter = priorityFilter
      const res = await listTickets(params)
      setTickets(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadTickets() }, [statusFilter, priorityFilter])

  const handleCreate = async (e) => {
    e.preventDefault()
    await createTicket(form)
    setShowForm(false)
    setForm({ title: '', description: '', priority: 'normal' })
    loadTickets()
  }

  const handleStatusChange = async (ticket, newStatus) => {
    await updateTicket(ticket.id, { status: newStatus })
    loadTickets()
    if (detail?.id === ticket.id) {
      setDetail({ ...detail, status: newStatus })
    }
  }

  const handlePriorityChange = async (ticket, newPriority) => {
    await updateTicket(ticket.id, { priority: newPriority })
    loadTickets()
    if (detail?.id === ticket.id) {
      setDetail({ ...detail, priority: newPriority })
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('确认删除该工单？')) return
    try {
      await deleteTicket(id)
      setDetail(null)
      loadTickets()
    } catch (err) {
      alert(err.response?.data?.detail || '删除失败')
    }
  }

  return (
    <div className="space-y-6">
      {/* 顶部 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">工单中心</h2>
          <p className="text-sm text-gray-400 mt-0.5">跟踪和管理售后问题工单</p>
        </div>
        <button onClick={() => setShowForm(true)} className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark">
          + 新建工单
        </button>
      </div>

      {/* 筛选 */}
      <div className="flex gap-4 flex-wrap">
        <div className="flex gap-1">
          <button onClick={() => setStatusFilter('')}
            className={`px-3 py-1 text-xs rounded-full border ${!statusFilter ? 'bg-primary text-white border-primary' : 'border-gray-200 text-gray-500'}`}>
            全部状态
          </button>
          {STATUS_OPTIONS.map((s) => (
            <button key={s} onClick={() => setStatusFilter(s)}
              className={`px-3 py-1 text-xs rounded-full border ${statusFilter === s ? 'bg-primary text-white border-primary' : 'border-gray-200 text-gray-500'}`}>
              {STATUS_MAP[s].label}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {PRIORITY_OPTIONS.map((p) => (
            <button key={p} onClick={() => setPriorityFilter(priorityFilter === p ? '' : p)}
              className={`px-3 py-1 text-xs rounded-full border ${priorityFilter === p ? 'bg-gray-700 text-white border-gray-700' : 'border-gray-200 text-gray-500'}`}>
              {PRIORITY_MAP[p].label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex gap-6">
        {/* 工单列表 */}
        <div className="flex-1 bg-white rounded-xl shadow-sm overflow-hidden">
          {loading ? (
            <div className="p-8 text-center text-gray-400 text-sm">加载中...</div>
          ) : tickets.length === 0 ? (
            <div className="p-8 text-center text-gray-400 text-sm">暂无工单</div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500">
                <tr>
                  <th className="text-left px-5 py-3 font-medium">工单</th>
                  <th className="text-left px-5 py-3 font-medium">状态</th>
                  <th className="text-left px-5 py-3 font-medium">优先级</th>
                  <th className="text-left px-5 py-3 font-medium">负责人</th>
                  <th className="text-left px-5 py-3 font-medium">更新时间</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {tickets.map((t) => (
                  <tr key={t.id} onClick={() => setDetail(t)}
                    className={`hover:bg-gray-50 cursor-pointer ${detail?.id === t.id ? 'bg-primary-light/50' : ''}`}>
                    <td className="px-5 py-3">
                      <p className="font-medium text-gray-800">{t.title}</p>
                      {t.customer_name && <p className="text-xs text-gray-400">客户：{t.customer_name}</p>}
                    </td>
                    <td className="px-5 py-3">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_MAP[t.status]?.color || ''}`}>
                        {STATUS_MAP[t.status]?.label || t.status}
                      </span>
                    </td>
                    <td className="px-5 py-3">
                      <span className={`text-xs ${PRIORITY_MAP[t.priority]?.color || ''}`}>
                        {PRIORITY_MAP[t.priority]?.label || t.priority}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-gray-500 text-xs">{t.assignee_name || '—'}</td>
                    <td className="px-5 py-3 text-gray-400 text-xs">{new Date(t.updated_at).toLocaleString('zh-CN')}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* 工单详情侧栏 */}
        {detail && (
          <div className="w-80 bg-white rounded-xl shadow-sm p-5 flex-shrink-0">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-800">工单详情</h3>
              <button onClick={() => setDetail(null)} className="text-gray-400 hover:text-gray-600 text-xs">关闭</button>
            </div>

            <h4 className="text-base font-medium text-gray-800 mb-2">{detail.title}</h4>
            <p className="text-sm text-gray-600 mb-4 whitespace-pre-wrap">{detail.description || '无描述'}</p>

            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-400">状态</span>
                <select value={detail.status} onChange={(e) => handleStatusChange(detail, e.target.value)}
                  className="text-xs border border-gray-200 rounded px-2 py-1">
                  {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{STATUS_MAP[s].label}</option>)}
                </select>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">优先级</span>
                <select value={detail.priority} onChange={(e) => handlePriorityChange(detail, e.target.value)}
                  className="text-xs border border-gray-200 rounded px-2 py-1">
                  {PRIORITY_OPTIONS.map((p) => <option key={p} value={p}>{PRIORITY_MAP[p].label}</option>)}
                </select>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">负责人</span>
                <span className="text-gray-600">{detail.assignee_name || '—'}</span>
              </div>
              {detail.customer_name && (
                <div className="flex justify-between">
                  <span className="text-gray-400">关联客户</span>
                  <span className="text-gray-600">{detail.customer_name}</span>
                </div>
              )}
              <div className="flex justify-between">
                <span className="text-gray-400">创建时间</span>
                <span className="text-gray-500 text-xs">{new Date(detail.created_at).toLocaleString('zh-CN')}</span>
              </div>
            </div>

            <button onClick={() => handleDelete(detail.id)}
              className="mt-6 w-full text-xs text-red-500 border border-red-200 rounded-lg py-2 hover:bg-red-50">
              删除工单
            </button>
          </div>
        )}
      </div>

      {/* 新建工单弹窗 */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-base font-semibold text-gray-800 mb-4">新建工单</h3>
            <form onSubmit={handleCreate} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">标题 *</label>
                <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                  placeholder="如：客户要求换货"
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">描述</label>
                <textarea rows={4} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="详细描述问题..."
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">优先级</label>
                <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary">
                  {PRIORITY_OPTIONS.map((p) => <option key={p} value={p}>{PRIORITY_MAP[p].label}</option>)}
                </select>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-500">取消</button>
                <button type="submit" className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark">创建</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
