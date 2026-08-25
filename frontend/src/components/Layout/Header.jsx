import { useEffect, useState } from 'react'
import { useAuth } from '../../context/AuthContext'
import { useLocation, useNavigate } from 'react-router-dom'
import { listConversations } from '../../api/conversations'

export default function Header() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [waitingCount, setWaitingCount] = useState(0)

  useEffect(() => {
    if (!user) return undefined
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
  }, [user])

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  const showWaitingBanner = waitingCount > 0 && !location.pathname.startsWith('/conversations')

  return (
    <div className="flex-shrink-0">
      <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
        <div>
          <h1 className="text-gray-700 text-base font-medium">AI售后客服协同工作台</h1>
        </div>

        <div className="flex items-center gap-4">
          {waitingCount > 0 && (
            <button
              type="button"
              onClick={() => navigate('/conversations')}
              className="hidden sm:inline-flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-orange-50 text-orange-600 border border-orange-200 hover:bg-orange-100"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-orange-500 animate-pulse" />
              {waitingCount} 待人工
            </button>
          )}
          {user && (
            <>
              <div className="text-right">
                <p className="text-sm font-medium text-gray-700">
                  {user.display_name || user.username}
                </p>
                <p className="text-xs text-gray-400">{user.company_name}</p>
              </div>
              <div className="w-8 h-8 rounded-full bg-primary flex items-center justify-center text-white text-sm font-bold">
                {(user.display_name || user.username).charAt(0).toUpperCase()}
              </div>
              <button
                onClick={handleLogout}
                className="text-sm text-gray-500 hover:text-red-500 transition-colors"
              >
                退出
              </button>
            </>
          )}
        </div>
      </header>

      {showWaitingBanner && (
        <div className="px-6 py-2 bg-orange-50 border-b border-orange-200 flex items-center justify-between">
          <p className="text-sm text-orange-700">
            有 <span className="font-semibold">{waitingCount}</span> 条会话待人工接入
          </p>
          <button
            type="button"
            onClick={() => navigate('/conversations')}
            className="text-xs px-3 py-1 bg-orange-500 text-white rounded-lg hover:bg-orange-600"
          >
            去处理
          </button>
        </div>
      )}
    </div>
  )
}
