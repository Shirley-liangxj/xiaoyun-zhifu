import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import MainLayout from './components/Layout/MainLayout'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Conversations from './pages/Conversations'
import Knowledge from './pages/Knowledge'
import Tickets from './pages/Tickets'

// 路由守卫：未登录跳转登录页
function PrivateRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-primary text-sm">加载中...</div>
      </div>
    )
  }
  return user ? children : <Navigate to="/login" replace />
}

// 已登录用户访问登录/注册页时跳转首页
function PublicRoute({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  return user ? <Navigate to="/" replace /> : children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* 公开路由 */}
          <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />

          {/* 受保护路由 */}
          <Route
            path="/"
            element={
              <PrivateRoute>
                <MainLayout />
              </PrivateRoute>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="conversations" element={<Conversations />} />
            <Route path="tickets" element={<Tickets />} />
            <Route path="knowledge" element={<Knowledge />} />
            <Route path="settings" element={<PlaceholderPage title="系统设置" />} />
          </Route>

          {/* 404 */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}

// 阶段B功能占位页
function PlaceholderPage({ title }) {
  return (
    <div className="bg-white rounded-xl shadow-sm p-8 text-center">
      <p className="text-4xl mb-4">🚧</p>
      <h2 className="text-lg font-semibold text-gray-700">{title}</h2>
      <p className="text-gray-400 text-sm mt-2">该功能将在后续阶段上线</p>
    </div>
  )
}
