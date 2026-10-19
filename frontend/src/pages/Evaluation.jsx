import { useState } from 'react'
import { runAgentEval, runEval } from '../api/eval'

function confidenceColor(c) {
  if (c >= 0.7) return 'text-green-600'
  if (c >= 0.4) return 'text-yellow-600'
  return 'text-red-500'
}

function behaviorBadge(correct) {
  if (correct === true) return 'text-green-600'
  if (correct === false) return 'text-red-500'
  return 'text-gray-400'
}

export default function Evaluation() {
  const [report, setReport] = useState(null)
  const [agentReport, setAgentReport] = useState(null)
  const [loading, setLoading] = useState(false)
  const [agentLoading, setAgentLoading] = useState(false)
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

  const handleRunAgent = async () => {
    setAgentLoading(true)
    setError('')
    try {
      const res = await runAgentEval()
      setAgentReport(res.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Agent 控制层评测失败')
    } finally {
      setAgentLoading(false)
    }
  }

  const cm = report?.confusion_matrix

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-800">RAG 评测基线</h2>
          <p className="text-sm text-gray-400 mt-0.5">
            40 题售后回归评测集（演示环境）· 检索质量 + 转人工判断 + 阈值混淆矩阵
          </p>
        </div>
        <button onClick={handleRun} disabled={loading}
          className="px-5 py-2 text-sm bg-primary text-white rounded-lg hover:bg-primary-dark disabled:opacity-60">
          {loading ? '评测中...' : '运行评测'}
        </button>
        <button onClick={handleRunAgent} disabled={agentLoading}
          className="ml-2 px-5 py-2 text-sm border border-primary text-primary rounded-lg hover:bg-primary-light disabled:opacity-60">
          {agentLoading ? 'Agent 评测中...' : '运行 Agent 评测'}
        </button>
      </div>

      {error && (
        <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-lg">{error}</div>
      )}

      {report && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {[
              { title: '检索命中率', value: `${report.retrieval_hit_rate}%`, desc: `${report.total} 题`, color: 'text-blue-600' },
              { title: '关键词覆盖达标率', value: `${report.keyword_coverage_rate}%`, desc: '应答题 · 仅代表检索文本覆盖，不等于生成答案正确', color: 'text-indigo-600' },
              { title: '转人工判断准确率', value: `${report.transfer_judgment_accuracy}%`, desc: '行为与期望一致', color: 'text-primary' },
              { title: '转人工准确率', value: `${report.transfer_accuracy_rate}%`, desc: '超出范围类转对率', color: 'text-orange-600' },
              { title: '平均置信度', value: report.avg_confidence, desc: `阈值 ${report.confidence_threshold ?? 0.6}`, color: 'text-gray-700' },
            ].map((c) => (
              <div key={c.title} className="bg-white rounded-xl shadow-sm p-5">
                <p className="text-sm text-gray-500 mb-1">{c.title}</p>
                <p className={`text-2xl font-bold ${c.color}`}>{c.value}</p>
                <p className="text-xs text-gray-400 mt-1">{c.desc}</p>
              </div>
            ))}
          </div>

          {cm && (
            <div className="bg-white rounded-xl shadow-sm p-5">
              <h3 className="text-sm font-semibold text-gray-700 mb-3">
                阈值混淆矩阵（confidence ≥ {report.confidence_threshold ?? 0.6} 为「直接回答」）
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="border border-red-100 bg-red-50 rounded-lg p-4">
                  <p className="text-xs text-red-600 mb-1">误转（本该答却转了）</p>
                  <p className="text-2xl font-bold text-red-600">{cm.false_transfer_count}</p>
                  <p className="text-xs text-red-400 mt-1">{cm.false_transfer_rate}% / 应答题</p>
                </div>
                <div className="border border-orange-100 bg-orange-50 rounded-lg p-4">
                  <p className="text-xs text-orange-600 mb-1">漏转（本该转却答了）</p>
                  <p className="text-2xl font-bold text-orange-600">{cm.missed_transfer_count}</p>
                  <p className="text-xs text-orange-400 mt-1">{cm.missed_transfer_rate}% / 应转题</p>
                </div>
                <div className="border border-green-100 bg-green-50 rounded-lg p-4">
                  <p className="text-xs text-green-600 mb-1">行为判断正确</p>
                  <p className="text-2xl font-bold text-green-600">{cm.correct_count}</p>
                  <p className="text-xs text-green-400 mt-1">/ {report.total} 题</p>
                </div>
                <div className="border border-gray-100 bg-gray-50 rounded-lg p-4">
                  <p className="text-xs text-gray-600 mb-1">高置信率</p>
                  <p className="text-2xl font-bold text-gray-700">{report.high_confidence_rate}%</p>
                  <p className="text-xs text-gray-400 mt-1">≥ 阈值</p>
                </div>
              </div>
            </div>
          )}

          {report.category_stats?.length > 0 && (
            <div className="bg-white rounded-xl shadow-sm overflow-hidden">
              <div className="px-5 py-3 border-b border-gray-100">
                <h3 className="text-sm font-semibold text-gray-700">各分层表现</h3>
              </div>
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-500">
                  <tr>
                    <th className="text-left px-5 py-2 font-medium">分类</th>
                    <th className="text-left px-5 py-2 font-medium">题数</th>
                    <th className="text-left px-5 py-2 font-medium">行为准确率</th>
                    <th className="text-left px-5 py-2 font-medium">关键词覆盖达标率</th>
                    <th className="text-left px-5 py-2 font-medium">转人工准确率</th>
                    <th className="text-left px-5 py-2 font-medium">误转</th>
                    <th className="text-left px-5 py-2 font-medium">漏转</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-50">
                  {report.category_stats.map((s) => (
                    <tr key={s.category} className="hover:bg-gray-50">
                      <td className="px-5 py-2.5 font-medium text-gray-800">{s.category}</td>
                      <td className="px-5 py-2.5 text-gray-500">{s.total}</td>
                      <td className="px-5 py-2.5">{s.behavior_accuracy}%</td>
                      <td className="px-5 py-2.5">{s.keyword_coverage != null ? `${s.keyword_coverage}%` : '—'}</td>
                      <td className="px-5 py-2.5">{s.transfer_accuracy != null ? `${s.transfer_accuracy}%` : '—'}</td>
                      <td className="px-5 py-2.5 text-red-500">{s.false_transfer}</td>
                      <td className="px-5 py-2.5 text-orange-500">{s.missed_transfer}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

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
                  <th className="text-left px-5 py-2 font-medium">期望/实际</th>
                  <th className="text-left px-5 py-2 font-medium">行为</th>
                  <th className="text-left px-5 py-2 font-medium">置信度</th>
                  <th className="text-left px-5 py-2 font-medium">来源</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {report.results.map((r) => (
                  <tr key={r.id} className="hover:bg-gray-50">
                    <td className="px-5 py-2.5 text-gray-400">{r.id}</td>
                    <td className="px-5 py-2.5 text-gray-800 max-w-xs truncate" title={r.question}>{r.question}</td>
                    <td className="px-5 py-2.5">
                      <span className="text-xs px-2 py-0.5 bg-gray-100 rounded-full">{r.category}</span>
                    </td>
                    <td className="px-5 py-2.5 text-xs text-gray-500">
                      {r.expected_behavior || '—'} → {r.actual_behavior || '—'}
                    </td>
                    <td className={`px-5 py-2.5 text-xs font-medium ${behaviorBadge(r.behavior_correct)}`}>
                      {r.behavior_correct ? '✓' : '✗'}
                    </td>
                    <td className={`px-5 py-2.5 font-medium ${confidenceColor(r.confidence)}`}>
                      {(r.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="px-5 py-2.5 text-xs text-gray-500">{r.top_source || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {agentReport && (
        <div className="bg-white rounded-xl shadow-sm p-5">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div>
              <h3 className="text-sm font-semibold text-gray-700">Agent 主循环离线回归</h3>
              <p className="text-xs text-gray-400 mt-1">{agentReport.message}</p>
            </div>
            <span className="text-xs px-2 py-1 rounded-full bg-blue-50 text-blue-700">{agentReport.execution_mode}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
            <div><p className="text-xs text-gray-500">工具序列</p><p className="text-xl font-semibold text-primary">{agentReport.tool_sequence_accuracy}%</p></div>
            <div><p className="text-xs text-gray-500">参数抽取</p><p className="text-xl font-semibold text-primary">{agentReport.parameter_accuracy}%</p></div>
            <div><p className="text-xs text-gray-500">必要追问</p><p className="text-xl font-semibold text-primary">{agentReport.followup_accuracy}%</p></div>
            <div><p className="text-xs text-gray-500">终态命中</p><p className="text-xl font-semibold text-primary">{agentReport.terminal_state_accuracy}%</p></div>
            <div><p className="text-xs text-gray-500">高危漏放</p><p className="text-xl font-semibold text-red-600">{agentReport.high_risk_missed_count}</p></div>
            <div><p className="text-xs text-gray-500">误转</p><p className="text-xl font-semibold text-orange-600">{agentReport.false_transfer_count}</p></div>
            <div><p className="text-xs text-gray-500">受控回归通过</p><p className="text-xl font-semibold text-primary">{agentReport.end_to_end_success_rate}%</p></div>
          </div>
          <p className="text-[11px] text-gray-400 mt-3">mock 仅替代外部 LLM/RAG 返回；Agent 循环、工具注册、数据库状态与中断分支真实执行。该结果不能外推为真实模型线上准确率。</p>
          <div className="overflow-x-auto mt-4 border border-gray-100 rounded-lg">
            <table className="w-full text-xs">
              <thead className="bg-gray-50 text-gray-500">
                <tr>
                  <th className="text-left px-3 py-2">场景</th>
                  <th className="text-left px-3 py-2">工具轨迹</th>
                  <th className="text-left px-3 py-2">终态</th>
                  <th className="text-left px-3 py-2">LLM 次数</th>
                  <th className="text-left px-3 py-2">结果</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {agentReport.results?.map((row) => (
                  <tr key={row.id}>
                    <td className="px-3 py-2 max-w-xs" title={row.reason}>{row.id} · {row.input}</td>
                    <td className="px-3 py-2 text-gray-600">{row.tool_sequence.length ? row.tool_sequence.join(' → ') : '无工具'}</td>
                    <td className="px-3 py-2">{row.terminal_state}</td>
                    <td className="px-3 py-2">{row.trajectory?.llm_calls ?? '—'}</td>
                    <td className={`px-3 py-2 font-medium ${row.passed ? 'text-green-600' : 'text-red-500'}`}>
                      {row.passed ? '通过' : row.failure_reason || '失败'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {!report && !loading && (
        <div className="bg-white rounded-xl shadow-sm p-12 text-center">
          <p className="text-4xl mb-3">📊</p>
          <p className="text-gray-500 text-sm">点击「运行评测」开始 RAG 基线测试</p>
          <p className="text-gray-400 text-xs mt-2">RAG 评测需完成知识库索引；Agent 离线评测不调用外部模型</p>
        </div>
      )}
    </div>
  )
}
