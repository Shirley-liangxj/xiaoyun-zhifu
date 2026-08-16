import { useState, useEffect } from 'react'
import { listDocs, createDoc, updateDoc, deleteDoc, searchKnowledge, reindexAll } from '../api/knowledge'

const CATEGORIES = ['通用', '退换货', '物流', '尺码', '支付', '售后政策']

export default function Knowledge() {
  const [docs, setDocs] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ title: '', content: '', category: '通用' })
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResults, setSearchResults] = useState(null)
  const [searching, setSearching] = useState(false)
  const [filterCategory, setFilterCategory] = useState('')

  const loadDocs = async () => {
    setLoading(true)
    try {
      const res = await listDocs(filterCategory || undefined)
      setDocs(res.data)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadDocs() }, [filterCategory])

  const openCreate = () => {
    setEditing(null)
    setForm({ title: '', content: '', category: '通用' })
    setShowForm(true)
  }

  const openEdit = (doc) => {
    setEditing(doc)
    setForm({ title: doc.title, content: doc.content, category: doc.category })
    setShowForm(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (editing) {
      await updateDoc(editing.id, form)
    } else {
      await createDoc(form)
    }
    setShowForm(false)
    loadDocs()
  }

  const handleDelete = async (id) => {
    if (!confirm('确认删除该文档？')) return
    await deleteDoc(id)
    loadDocs()
  }

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!searchQuery.trim()) return
    setSearching(true)
    try {
      const res = await searchKnowledge(searchQuery)
      setSearchResults(res.data)
    } catch (err) {
      alert(err.response?.data?.detail || '检索失败，请检查 API Key 配置')
    } finally {
      setSearching(false)
    }
  }

  const handleReindex = async () => {
    try {
      const res = await reindexAll()
      alert(res.data.message + `，共索引 ${res.data.indexed_count} 篇`)
      loadDocs()
    } catch (err) {
      alert(err.response?.data?.detail || '重建索引失败')
    }
  }

  return (
    <div className="space-y-6">
      {/* 顶部操作栏 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">知识库管理</h2>
          <p className="text-sm text-gray-400 mt-0.5">管理售后知识文档，支持 RAG 向量检索</p>
        </div>
        <div className="flex gap-2">
          <button onClick={handleReindex} className="px-4 py-2 text-sm border border-gray-200 rounded-lg hover:bg-gray-50 text-gray-600">
            重建索引
          </button>
          <button onClick={openCreate} className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark">
            + 新增文档
          </button>
        </div>
      </div>

      {/* 分类筛选 */}
      <div className="flex gap-2 flex-wrap">
        <button
          onClick={() => setFilterCategory('')}
          className={`px-3 py-1 text-xs rounded-full border ${!filterCategory ? 'bg-primary text-white border-primary' : 'border-gray-200 text-gray-500'}`}
        >
          全部
        </button>
        {CATEGORIES.map((c) => (
          <button
            key={c}
            onClick={() => setFilterCategory(c)}
            className={`px-3 py-1 text-xs rounded-full border ${filterCategory === c ? 'bg-primary text-white border-primary' : 'border-gray-200 text-gray-500'}`}
          >
            {c}
          </button>
        ))}
      </div>

      {/* 文档列表 */}
      <div className="bg-white rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-8 text-center text-gray-400 text-sm">加载中...</div>
        ) : docs.length === 0 ? (
          <div className="p-8 text-center text-gray-400 text-sm">暂无文档，点击「新增文档」开始添加</div>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-gray-500">
              <tr>
                <th className="text-left px-5 py-3 font-medium">标题</th>
                <th className="text-left px-5 py-3 font-medium">分类</th>
                <th className="text-left px-5 py-3 font-medium">索引状态</th>
                <th className="text-left px-5 py-3 font-medium">更新时间</th>
                <th className="text-right px-5 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {docs.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-5 py-3 font-medium text-gray-800">{doc.title}</td>
                  <td className="px-5 py-3">
                    <span className="px-2 py-0.5 bg-primary-light text-primary-dark text-xs rounded-full">{doc.category}</span>
                  </td>
                  <td className="px-5 py-3">
                    <span className={`text-xs ${doc.is_indexed ? 'text-green-600' : 'text-gray-400'}`}>
                      {doc.is_indexed ? '已索引' : '未索引'}
                    </span>
                  </td>
                  <td className="px-5 py-3 text-gray-400">{new Date(doc.updated_at).toLocaleString('zh-CN')}</td>
                  <td className="px-5 py-3 text-right space-x-2">
                    <button onClick={() => openEdit(doc)} className="text-primary hover:underline text-xs">编辑</button>
                    <button onClick={() => handleDelete(doc.id)} className="text-red-500 hover:underline text-xs">删除</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* RAG 检索测试 */}
      <div className="bg-white rounded-xl shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">RAG 检索测试</h3>
        <form onSubmit={handleSearch} className="flex gap-2">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="输入客户问题，测试知识库检索效果..."
            className="flex-1 px-4 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary"
          />
          <button type="submit" disabled={searching} className="px-5 py-2 bg-primary text-white text-sm rounded-lg hover:bg-primary-dark disabled:opacity-60">
            {searching ? '检索中...' : '检索'}
          </button>
        </form>
        {searchResults && (
          <div className="mt-4 space-y-3">
            <p className="text-xs text-gray-400">查询：「{searchResults.query}」— 找到 {searchResults.results.length} 条相关结果</p>
            {searchResults.results.map((r, i) => (
              <div key={i} className="border border-gray-100 rounded-lg p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-primary">{r.title}</span>
                  <span className="text-xs text-gray-400">相似度 {(r.score * 100).toFixed(1)}%</span>
                </div>
                <p className="text-sm text-gray-600">{r.text}</p>
                <span className="text-xs text-gray-300 mt-1 inline-block">{r.category}</span>
              </div>
            ))}
            {searchResults.results.length === 0 && (
              <p className="text-sm text-gray-400">未找到相关内容，请先添加并索引知识库文档</p>
            )}
          </div>
        )}
      </div>

      {/* 新增/编辑弹窗 */}
      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg p-6">
            <h3 className="text-base font-semibold text-gray-800 mb-4">{editing ? '编辑文档' : '新增文档'}</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">标题</label>
                <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">分类</label>
                <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary">
                  {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">内容</label>
                <textarea required rows={8} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none" />
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700">取消</button>
                <button type="submit" className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark">保存</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
