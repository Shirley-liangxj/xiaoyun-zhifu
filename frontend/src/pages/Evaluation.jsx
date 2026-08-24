import { useState } from 'react'
import { runEval } from '../api/eval'

function confidenceColor(c) {
  if (c >= 0.7) return 'text-green-600'
  if (c >= 0.4) return 'text-yellow-600'
  return 'text-red-500'
}

export default function Evaluation() {
  const [report, setReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleRun = async () => {
    setLoading(true)
    setError('')
    try {
      const res = await runEval()
      setReport(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || '评测失败，请检查 API Key 和知识库索引')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">RAG 评测基线</h2>
          <p className="text-sm text-gray-400 mt-0.5">基于 17 道服饰售后标准问题，验证知识库检索效果</p>
        </div>
        <button onClick={handleRun} disabled={loading}
          className="px-5 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-60">
          {loading ? '评测中...' : '运行评测'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{error}</div>
      )}

      {report && (
        <>
          {/* 汇总指标 */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { title: '检索命中率', value: `${report.retrieval_hit_rate}%`, desc: `${report.total} 题中有结果`, color: 'text-blue-600' },
              { title: '平均置信度', value: report.avg_confidence, desc: '0~1 分值', color: 'text-primary' },
              { title: '高置信率', value: `${report.high_confidence_rate}%`, desc: `置信度 ≥ ${report.confidence_threshold ?? 0.6}`, color: 'text-green-600' },
            ].map((c) => (
              <div key={c.title} className="bg-white rounded-xl shadow-sm p-5">
                <p className="text-sm text-gray-500 mb-1">{c.title}</p>
                <p className={`text-3xl font-bold ${c.color}`}>{c.value}</p>
                <p className="text-xs text-gray-400 mt-1">{c.desc}</p>
              </div>
            ))}
          </div>

          {/* 逐题结果 */}
          <div className="bg-white rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-3 border-b border-gray-100">
              <h3 className="text-sm font-semibold text-gray-700">逐题评测结果</h3>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-gray-500">
                <tr>
                  <th className="text-left px-5 py-2 font-medium">#</th>
                  <th className="text-left px-5 py-2 font-medium">问题</th>
                  <th className="text-left px-5 py-2 font-medium">分类</th>
                  <th className="text-left px-5 py-2 font-medium">命中</th>
                  <th className="text-left px-5 py-2 font-medium">置信度</th>
                  <th className="text-left px-5 py-2 font-medium">来源文档</th>
                  <th className="text-left px-5 py-2 font-medium">关键词</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {report.results.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-5 py-2.5 text-gray-400">{r.id}</td>
                    <td className="px-5 py-2.5 text-gray-800 max-w-xs">{r.question}</td>
                    <td className="px-5 py-2.5">
                      <span className="text-xs px-2 py-0.5 bg-gray-100 rounded-full">{r.category}</span>
                    </td>
                    <td className="px-5 py-2.5">
                      <span className={`text-xs ${r.retrieved ? 'text-green-600' : 'text-red-500'}`}>
                        {r.retrieved ? '✓' : '✗'}
                      </span>
                    </td>
                    <td className={`px-5 py-2.5 font-medium ${confidenceColor(r.confidence)}`}>
                      {(r.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="px-5 py-2.5 text-xs text-gray-500">{r.top_source || '—'}</td>
                    <td className="px-5 py-2.5 text-xs text-gray-400">
                      {r.keyword_hits?.length > 0 ? r.keyword_hits.join('、') : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {!report && !loading && (
        <div className="bg-white rounded-xl shadow-sm p-12 text-center">
          <p className="text-4xl mb-3">📊</p>
          <p className="text-gray-500 text-sm">点击「运行评测」开始 RAG 基线测试</p>
          <p className="text-gray-400 text-xs mt-2">请确保已添加知识库文档并完成索引</p>
        </div>
      )}
    </div>
  )
}
