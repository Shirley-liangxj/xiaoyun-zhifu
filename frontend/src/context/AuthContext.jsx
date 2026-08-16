import { createContext, useContext, useState, useEffect } from 'react'
import api from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // 初始化：检查本地令牌并获取用户信息
  useEffect(() => {
    const token = localStorage.getItem('token')
    if (token) {
      api.get('/api/users/me')
        .then((res) => {
          setUser(res.data)
        })
        .catch(() => {
          localStorage.removeItem('token')
        })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  // 登录
  const login = async (username, password) => {
    const res = await api.post('/api/auth/login', { username, password })
    const { access_token } = res.data
    localStorage.setItem('token', access_token)
    const userRes = await api.get('/api/users/me')
    setUser(userRes.data)
    return userRes.data
  }

  // 注册
  const register = async (data) => {
    const res = await api.post('/api/auth/register', data)
    const { access_token } = res.data
    localStorage.setItem('token', access_token)
    const userRes = await api.get('/api/users/me')
    setUser(userRes.data)
    return userRes.data
  }

  // 登出
  const logout = () => {
    localStorage.removeItem('token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth 必须在 AuthProvider 内使用')
  return ctx
}
