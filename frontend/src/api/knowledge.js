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
