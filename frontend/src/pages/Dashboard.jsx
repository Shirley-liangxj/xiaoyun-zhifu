import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { getDashboardStats } from '../api/stats'
import { resetDemoData } from '../api/settings'

/** 简易条形图组件 */
function BarChart({ data, colors }) {
  const max = Math.max(...Object.values(data), 1)
  return (
    <div className="space-y-2">
      {Object.entries(data).map(([key, val]) => (
        <div key={key} className="flex items-center gap-3">
          <span className="text-xs text-gray-500 w-16 text-right">{key}</span>
          <div className="flex-1 bg-gray-100 rounded-full h-5 overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${colors[key] || 'bg-gray-400'}`}
              style={{ width: `${(val / max) * 100}%` }}
            />
          </div>
          <span className="text-xs text-gray-600 w-6">{val}</span>
        </div>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [resetting, setResetting] = useState(false)

  const loadStats = () => {
    setLoading(true)
    return getDashboardStats()
      .then((res) => setStats(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { loadStats() }, [])

  const handleResetDemo = async () => {
    if (!confirm('将覆盖当前租户的演示知识库、会话与工单，确认继续？')) return
    setResetting(true)
    try {
      await resetDemoData()
      await loadStats()
      alert('演示数据已加载，可前往会话管理查看')
    } catch (err) {
      alert(err.response?.data?.detail || '加载演示数据失败')
    } finally {
      setResetting(false)
    }
  }

  const o = stats?.overview || {}
  const isEmpty = !loading && o.total_conversations === 0

  return (
    <div>
      <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-1">
          欢迎回来，{user?.display_name || user?.username}
        </h2>
        <p className="text-gray-400 text-sm">{user?.company_name} · AI售后客服协同工作台</p>
      </div>

      {isEmpty && user?.role === 'admin' && (
        <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 mb-6 flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-orange-800">暂无会话数据</p>
            <p className="text-xs text-orange-600 mt-1">可一键加载演示数据，或打开买家端 /chat 开始对话</p>
          </div>
          <button
            onClick={handleResetDemo}
            disabled={resetting}
            className="shrink-0 px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-60"
          >
            {resetting ? '加载中...' : '加载演示数据'}
          </button>
        </div>
      )}

      {loading ? (
        <div className="text-center text-gray-400 text-sm py-8">加载统计数据...</div>
      ) : (
        <>
          {/* 核心指标 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[
              { title: '总会话', value: o.total_conversations, sub: `${o.waiting_human_conversations || 0} 待人工 · ${o.active_conversations} 进行中`, color: 'text-blue-600' },
              { title: '总消息', value: o.total_messages, sub: '客户+坐席', color: 'text-indigo-600' },
              { title: '工单', value: o.total_tickets, sub: `${o.open_tickets} 待处理`, color: 'text-orange-600' },
              { title: '知识库', value: o.total_knowledge_docs, sub: `${o.indexed_docs} 已索引`, color: 'text-green-600' },
            ].map((c) => (
              <div key={c.title} className="bg-white rounded-xl shadow-sm p-5">
                <p className="text-sm text-gray-500 mb-1">{c.title}</p>
                <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
                <p className="text-xs text-gray-400 mt-1">{c.sub}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {/* AI 采纳率 */}
            <div className="bg-white rounded-xl shadow-sm p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">AI 建议采纳率</h3>
              <div className="flex items-end gap-2 mb-2">
                <span className="text-4xl font-bold text-primary">{o.ai_accept_rate}%</span>
              </div>
              <p className="text-xs text-gray-400">
                共生成 {o.ai_suggestions} 条建议，采纳 {o.ai_accepted} 条
              </p>
              <div className="mt-3 bg-gray-100 rounded-full h-2 overflow-hidden">
                <div className="h-full bg-primary rounded-full" style={{ width: `${o.ai_accept_rate}%` }} />
              </div>
            </div>

            {/* 工单状态分布 */}
            <div className="bg-white rounded-xl shadow-sm p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">工单状态分布</h3>
              {stats && (
                <BarChart
                  data={{
                    '待处理': stats.ticket_status.open,
                    '处理中': stats.ticket_status.in_progress,
                    '已解决': stats.ticket_status.resolved,
                    '已关闭': stats.ticket_status.closed,
                  }}
                  colors={{
                    '待处理': 'bg-orange-400',
                    '处理中': 'bg-blue-400',
                    '已解决': 'bg-green-400',
                    '已关闭': 'bg-gray-400',
                  }}
                />
              )}
            </div>

            {/* 工单优先级分布 */}
            <div className="bg-white rounded-xl shadow-sm p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">工单优先级分布</h3>
              {stats && (
                <BarChart
                  data={{
                    '低': stats.ticket_priority.low,
                    '普通': stats.ticket_priority.normal,
                    '高': stats.ticket_priority.high,
                    '紧急': stats.ticket_priority.urgent,
                  }}
                  colors={{
                    '低': 'bg-gray-300',
                    '普通': 'bg-blue-300',
                    '高': 'bg-orange-400',
                    '紧急': 'bg-red-500',
                  }}
                />
              )}
            </div>
          </div>

          <div className="bg-primary-light rounded-xl p-5 border border-primary/20">
            <p className="text-primary-dark font-medium text-sm">小云智服 v1.1 — 买家进线 · 转人工 · 坐席协同</p>
            <p className="text-primary-dark/70 text-sm mt-1">
              演示：打开 <a href="/chat" target="_blank" rel="noreferrer" className="underline">买家端</a> 提问 → 低置信转人工 → 坐席在「会话管理」接入回复。
            </p>
          </div>
        </>
      )}
    </div>
  )
}
