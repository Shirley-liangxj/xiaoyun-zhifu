import api from './client'

/** 获取知识库文档列表 */
export const listDocs = (category) =>
  api.get('/api/knowledge/', { params: category ? { category } : {} })

/** 创建文档 */
export const createDoc = (data) => api.post('/api/knowledge/', data)

/** 获取文档详情 */
export const getDoc = (id) => api.get(`/api/knowledge/${id}`)

/** 更新文档 */
export const updateDoc = (id, data) => api.put(`/api/knowledge/${id}`, data)

/** 删除文档 */
export const deleteDoc = (id) => api.delete(`/api/knowledge/${id}`)

/** RAG 知识检索 */
export const searchKnowledge = (query, topK = 5) =>
  api.post('/api/knowledge/search', { query, top_k: topK })

/** 重建全部索引 */
export const reindexAll = () => api.post('/api/knowledge/reindex')

/** 获取知识缺口列表 */
export const listGaps = (status) =>
  api.get('/api/knowledge/gaps', { params: status ? { status_filter: status } : {} })

/** 解决知识缺口 */
export const resolveGap = (id, suggested_answer) =>
  api.post(`/api/knowledge/gaps/${id}/resolve`, { suggested_answer })

/** 忽略知识缺口 */
export const ignoreGap = (id) => api.post(`/api/knowledge/gaps/${id}/ignore`)
