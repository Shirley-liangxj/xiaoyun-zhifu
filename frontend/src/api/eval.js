import api from './client'

/**
 * RAG 评测会逐题做向量检索（40 题），Agent 评测会逐例跑主循环（12 例），
 * 耗时在分钟级，远超 axios 默认的 10s 超时。这里单独放宽到 180s，
 * 避免前端先断开、后端仍在空跑并重复消耗 embedding 调用。
 */
const EVAL_TIMEOUT_MS = 180000

/** 运行 RAG 评测 */
export const runEval = () => api.post('/api/eval/run', null, { timeout: EVAL_TIMEOUT_MS })

/** 运行 Agent 主循环离线评测 */
export const runAgentEval = () => api.post('/api/eval/agent', null, { timeout: EVAL_TIMEOUT_MS })

/** 把评测错误转成可展示文案：区分超时、网络失败与后端返回的具体原因 */
export function evalErrorMessage(err, fallback) {
  if (err.code === 'ECONNABORTED') {
    return '评测超时，请稍后重试；首次运行还需等待知识库索引'
  }
  if (!err.response) {
    return '网络异常，未能连接评测服务'
  }
  return err.response?.data?.detail || fallback
}