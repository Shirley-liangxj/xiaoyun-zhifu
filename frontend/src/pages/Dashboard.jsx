import { useState, useEffect } from 'react'
import { useAuth } from '../context/AuthContext'
import { getDashboardStats } from '../api/stats'

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

  useEffect(() => {
    getDashboardStats()
      .then((res) => setStats(res.data))
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const o = stats?.overview || {}

  return (
    <div>
      <div className="bg-white rounded-xl shadow-sm p-6 mb-6">
        <h2 className="text-xl font-semibold text-gray-800 mb-1">
          欢迎回来，{user?.display_name || user?.username}
        </h2>
        <p className="text-gray-400 text-sm">{user?.company_name} · AI售后客服协同工作台</p>
      </div>

      {loading ? (
        <div className="text-center text-gray-400 text-sm py-8">加载统计数据...</div>
      ) : (
        <>
          {/* 核心指标 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {[
              { title: '总会话', value: o.total_conversations, sub: `${o.active_conversations} 进行中`, color: 'text-blue-600' },
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
            <p className="text-primary-dark font-medium text-sm">小云智服 v1.0 — 全部功能已上线</p>
            <p className="text-primary-dark/70 text-sm mt-1">
              会话管理 · 知识库 RAG · AI 回复建议 · 工单系统 · 数据统计看板，一站式 AI 售后客服协同工作台。
            </p>
          </div>
        </>
      )}
    </div>
  )
}
