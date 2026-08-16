import api from './client'

/** 运行 RAG 评测 */
export const runEval = () => api.post('/api/eval/run')
