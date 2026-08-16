import { useState, useEffect } from 'react'
import { getSettings, updateSettings, getSystemStatus, testApi, reindexKnowledge, updateCompany } from '../api/settings'

export default function Settings() {
  const [status, setStatus] = useState(null)
  const [settings, setSettings] = useState(null)
  const [companyName, setCompanyName] = useState('')
  const [apiTest, setApiTest] = useState(null)
  const [reindexMsg, setReindexMsg] = useState('')
  const [saving, setSaving] = useState(false)

  const load = async () => {
    const [statusRes, settingsRes] = await Promise.all([getSystemStatus(), getSettings()])
    setStatus(statusRes.data)
    setSettings(settingsRes.data)
    setCompanyName(statusRes.data.company_name)
  }

  useEffect(() => { load() }, [])

  const handleSaveSettings = async () => {
    setSaving(true)
    await updateSettings(settings)
    if (companyName !== status?.company_name) {
      await updateCompany(companyName)
    }
    await load()
    setSaving(false)
  }

  const handleTestApi = async () => {
    const res = await testApi()
    setApiTest(res.data)
  }

  const handleReindex = async () => {
    setReindexMsg('重建中...')
    const res = await reindexKnowledge()
    setReindexMsg(res.data.message + ` (${res.data.indexed_count} 篇)`)
    await load()
  }

  if (!status || !settings) return <div className="text-center text-gray-400 py-8">加载中...</div>

  return (
    <div className="space-y-6 max-w-3xl">
      <div>
        <h2 className="text-lg font-semibold text-gray-800">系统设置</h2>
        <p className="text-sm text-gray-400 mt-0.5">API 配置、企业信息、知识库管理</p>
      </div>

      {/* API 配置 */}
      <div className="bg-white rounded-xl shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">API 配置</h3>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-500">API Key</span>
            <span className={status.api_key_configured ? 'text-green-600' : 'text-red-500'}>
              {status.api_key_masked} {status.api_key_configured ? '✓' : '✗ 未配置'}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">对话模型</span>
            <span className="text-gray-700">{status.llm_model}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500">向量模型</span>
            <span className="text-gray-700">{status.embedding_model}</span>
          </div>
          <button onClick={handleTestApi} className="mt-2 px-4 py-2 text-xs border border-gray-200 rounded-lg hover:bg-gray-50">
            测试 API 连接
          </button>
          {apiTest && (
            <p className={`text-xs ${apiTest.status === 'ok' ? 'text-green-600' : 'text-red-500'}`}>
              {apiTest.message}
            </p>
          )}
        </div>
      </div>

      {/* 企业信息 */}
      <div className="bg-white rounded-xl shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">企业信息</h3>
        <div>
          <label className="block text-sm text-gray-600 mb-1">公司名称</label>
          <input value={companyName} onChange={(e) => setCompanyName(e.target.value)}
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm" />
        </div>
      </div>

      {/* 知识库索引 */}
      <div className="bg-white rounded-xl shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">知识库索引</h3>
        <div className="flex justify-between text-sm mb-3">
          <span className="text-gray-500">文档总数</span>
          <span>{status.knowledge_docs_total} 篇（已索引 {status.knowledge_docs_indexed} 篇）</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2 mb-3">
          <div className="bg-primary h-2 rounded-full transition-all"
            style={{ width: status.knowledge_docs_total ? `${(status.knowledge_docs_indexed / status.knowledge_docs_total) * 100}%` : '0%' }} />
        </div>
        <button onClick={handleReindex} className="px-4 py-2 text-xs border border-gray-200 rounded-lg hover:bg-gray-50">
          重建全部索引
        </button>
        {reindexMsg && <p className="text-xs text-gray-500 mt-2">{reindexMsg}</p>}
      </div>

      {/* 机器人设置 */}
      <div className="bg-white rounded-xl shadow-sm p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">机器人设置</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-600 mb-1">欢迎语</label>
            <textarea rows={2} value={settings.welcome_message}
              onChange={(e) => setSettings({ ...settings, welcome_message: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg text-sm resize-none" />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">
              置信度阈值（低于此值转人工）: {settings.confidence_threshold}
            </label>
            <input type="range" min="0.1" max="0.9" step="0.05"
              value={settings.confidence_threshold}
              onChange={(e) => setSettings({ ...settings, confidence_threshold: parseFloat(e.target.value) })}
              className="w-full" />
          </div>
          <div>
            <label className="block text-sm text-gray-600 mb-1">低置信度拒答话术</label>
            <textarea rows={2} value={settings.reject_message}
              onChange={(e) => setSettings({ ...settings, reject_message: e.target.value })}
              className="w-full px-3 py-2 border rounded-lg text-sm resize-none" />
          </div>
          <label className="flex items-center gap-2 text-sm text-gray-600">
            <input type="checkbox" checked={settings.auto_suggest}
              onChange={(e) => setSettings({ ...settings, auto_suggest: e.target.checked })} />
            客户消息后自动生成 AI 建议
          </label>
        </div>
      </div>

      <button onClick={handleSaveSettings} disabled={saving}
        className="px-6 py-2.5 bg-primary text-white text-sm rounded-lg hover:bg-primary-dark disabled:opacity-60">
        {saving ? '保存中...' : '保存设置'}
      </button>
    </div>
  )
}
