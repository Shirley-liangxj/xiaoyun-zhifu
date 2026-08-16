import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import MainLayout from './components/Layout/MainLayout'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import Conversations from './pages/Conversations'
import Knowledge from './pages/Knowledge'
import Tickets from './pages/Tickets'
import QuickReplies from './pages/QuickReplies'
import Settings from './pages/Settings'
import Evaluation from './pages/Evaluation'
import Chat from './pages/Chat'

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
          {/* 买家端 - 无需登录 */}
          <Route path="/chat" element={<Chat />} />

          {/* 公开路由 */}
          <Route path="/login" element={<PublicRoute><Login /></PublicRoute>} />
          <Route path="/register" element={<PublicRoute><Register /></PublicRoute>} />

          {/* 受保护路由 */}
          <Route path="/" element={<PrivateRoute><MainLayout /></PrivateRoute>}>
            <Route index element={<Dashboard />} />
            <Route path="conversations" element={<Conversations />} />
            <Route path="tickets" element={<Tickets />} />
            <Route path="knowledge" element={<Knowledge />} />
            <Route path="quick-replies" element={<QuickReplies />} />
            <Route path="evaluation" element={<Evaluation />} />
            <Route path="settings" element={<Settings />} />
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
