import { useState, useEffect } from 'react'
import { listQuickReplies, createQuickReply, updateQuickReply, deleteQuickReply } from '../api/quickReplies'

const CATEGORIES = ['退换货', '物流', '安抚', '催单']

export default function QuickReplies() {
  const [replies, setReplies] = useState([])
  const [filter, setFilter] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState({ category: '退换货', title: '', content: '' })

  const load = async () => {
    const res = await listQuickReplies(filter || undefined)
    setReplies(res.data)
  }

  useEffect(() => { load() }, [filter])

  const openCreate = () => {
    setEditing(null)
    setForm({ category: '退换货', title: '', content: '' })
    setShowForm(true)
  }

  const openEdit = (r) => {
    setEditing(r)
    setForm({ category: r.category, title: r.title, content: r.content })
    setShowForm(true)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (editing) await updateQuickReply(editing.id, form)
    else await createQuickReply(form)
    setShowForm(false)
    load()
  }

  const handleDelete = async (id) => {
    if (!confirm('确认删除？')) return
    await deleteQuickReply(id)
    load()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">快捷话术库</h2>
          <p className="text-sm text-gray-400 mt-0.5">坐席常用回复模板，支持一键插入会话</p>
        </div>
        <button onClick={openCreate} className="px-4 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark">
          + 新增话术
        </button>
      </div>

      <div className="flex gap-2">
        <button onClick={() => setFilter('')}
          className={`px-3 py-1 text-xs rounded-full border ${!filter ? 'bg-primary text-white border-primary' : 'border-gray-200 text-gray-500'}`}>
          全部
        </button>
        {CATEGORIES.map((c) => (
          <button key={c} onClick={() => setFilter(c)}
            className={`px-3 py-1 text-xs rounded-full border ${filter === c ? 'bg-primary text-white border-primary' : 'border-gray-200 text-gray-500'}`}>
            {c}
          </button>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {replies.map((r) => (
          <div key={r.id} className="bg-white rounded-xl shadow-sm p-4 border border-gray-100">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs px-2 py-0.5 bg-primary-light text-primary-dark rounded-full">{r.category}</span>
                <span className="text-sm font-medium text-gray-800">{r.title}</span>
              </div>
              <span className="text-xs text-gray-300">使用 {r.use_count} 次</span>
            </div>
            <p className="text-sm text-gray-600 mb-3 line-clamp-3">{r.content}</p>
            <div className="flex gap-2">
              <button onClick={() => openEdit(r)} className="text-xs text-primary hover:underline">编辑</button>
              <button onClick={() => handleDelete(r.id)} className="text-xs text-red-500 hover:underline">删除</button>
            </div>
          </div>
        ))}
      </div>

      {replies.length === 0 && (
        <div className="text-center text-gray-400 text-sm py-8">暂无话术，点击新增开始添加</div>
      )}

      {showForm && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6">
            <h3 className="text-base font-semibold mb-4">{editing ? '编辑话术' : '新增话术'}</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">分类</label>
                <select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg text-sm">
                  {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">标题</label>
                <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg text-sm" />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">内容</label>
                <textarea required rows={4} value={form.content} onChange={(e) => setForm({ ...form, content: e.target.value })}
                  className="w-full px-3 py-2 border rounded-lg text-sm resize-none" />
              </div>
              <div className="flex justify-end gap-2">
                <button type="button" onClick={() => setShowForm(false)} className="px-4 py-2 text-sm text-gray-500">取消</button>
                <button type="submit" className="px-4 py-2 text-sm bg-primary text-white rounded-lg">保存</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
