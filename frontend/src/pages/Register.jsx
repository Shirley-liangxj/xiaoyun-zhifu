import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    username: '',
    email: '',
    password: '',
    company_name: '',
    display_name: '',
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await register(form)
      navigate('/')
    } catch (err) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : '注册失败，请检查填写信息')
    } finally {
      setLoading(false)
    }
  }

  const handleChange = (field) => (e) => {
    setForm({ ...form, [field]: e.target.value })
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center py-8">
      <div className="bg-white rounded-2xl shadow-lg w-full max-w-md p-8">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary mb-4">
            <span className="text-white text-2xl">☁️</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-800">注册账号</h1>
          <p className="text-gray-400 text-sm mt-1">创建您的小云智服工作空间</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">公司名称 *</label>
            <input
              type="text"
              required
              value={form.company_name}
              onChange={handleChange('company_name')}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="如：某某服饰有限公司"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">用户名 *</label>
            <input
              type="text"
              required
              value={form.username}
              onChange={handleChange('username')}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="登录用户名"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">邮箱 *</label>
            <input
              type="email"
              required
              value={form.email}
              onChange={handleChange('email')}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="your@email.com"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">显示名称</label>
            <input
              type="text"
              value={form.display_name}
              onChange={handleChange('display_name')}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="客服姓名（可选）"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">密码 *</label>
            <input
              type="password"
              required
              minLength={6}
              value={form.password}
              onChange={handleChange('password')}
              className="w-full px-4 py-2.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent"
              placeholder="至少6位密码"
            />
          </div>

          {error && (
            <div className="bg-red-50 text-red-600 text-sm px-4 py-2.5 rounded-lg">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary hover:bg-primary-dark text-white font-medium py-2.5 rounded-lg transition-colors disabled:opacity-60"
          >
            {loading ? '注册中...' : '立即注册'}
          </button>
        </form>

        <p className="text-center text-sm text-gray-400 mt-6">
          已有账号？{' '}
          <Link to="/login" className="text-primary hover:underline font-medium">
            去登录
          </Link>
        </p>
      </div>
    </div>
  )
}
