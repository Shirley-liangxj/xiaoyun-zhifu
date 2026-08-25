import { useEffect, useState } from 'react'
import { NavLink } from 'react-router-dom'
import { listConversations } from '../../api/conversations'
import { useAuth } from '../../context/AuthContext'

const navItems = [
  { to: '/', label: '工作台', icon: '🏠' },
  { to: '/conversations', label: '会话管理', icon: '💬', badgeKey: 'waiting' },
  { to: '/tickets', label: '工单中心', icon: '📋' },
  { to: '/knowledge', label: '知识库', icon: '📚' },
  { to: '/quick-replies', label: '快捷话术', icon: '💡' },
  { to: '/evaluation', label: 'RAG评测', icon: '📊' },
  { to: '/settings', label: '系统设置', icon: '⚙️' },
]

export default function Sidebar() {
  const { user } = useAuth()
  const [waitingCount, setWaitingCount] = useState(0)
  const chatHref = user?.company_id ? `/chat?company_id=${user.company_id}` : '/chat'

  useEffect(() => {
    const load = async () => {
      try {
        const res = await listConversations('waiting_human')
        setWaitingCount(res.data.length)
      } catch {
        /* ignore */
      }
    }
    load()
    const timer = setInterval(load, 5000)
    return () => clearInterval(timer)
  }, [])

  return (
    <aside className="w-[220px] min-h-screen bg-sidebar flex flex-col flex-shrink-0">
      <div className="h-16 flex items-center px-5 border-b border-gray-700">
        <span className="text-white text-lg font-bold tracking-wide">小云智服</span>
      </div>

      <nav className="flex-1 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-5 py-3 text-sm transition-colors ${
                isActive
                  ? 'bg-primary text-white'
                  : 'text-gray-300 hover:bg-gray-700 hover:text-white'
              }`
            }
          >
            <span className="text-base">{item.icon}</span>
            <span className="flex-1">{item.label}</span>
            {item.badgeKey === 'waiting' && waitingCount > 0 && (
              <span className="min-w-[1.25rem] h-5 px-1.5 rounded-full bg-orange-500 text-white text-xs flex items-center justify-center">
                {waitingCount > 99 ? '99+' : waitingCount}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-gray-700">
        <p className="text-gray-500 text-xs">v1.1.0</p>
        <a href={chatHref} target="_blank" rel="noreferrer" className="text-xs text-primary-light hover:underline mt-1 block">买家端 ↗</a>
      </div>
    </aside>
  )
}
