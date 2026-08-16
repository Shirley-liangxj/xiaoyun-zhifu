import { useAuth } from '../../context/AuthContext'
import { useNavigate } from 'react-router-dom'

export default function Header() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <header className="h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6 flex-shrink-0">
      {/* 左侧：页面标题占位 */}
      <div>
        <h1 className="text-gray-700 text-base font-medium">AI售后客服协同工作台</h1>
      </div>

      {/* 右侧：用户信息 */}
      <div className="flex items-center gap-4">
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
  )
}
