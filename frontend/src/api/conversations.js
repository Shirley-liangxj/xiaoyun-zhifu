import api from './client'

/** 获取会话列表 */
export const listConversations = (status) =>
  api.get('/api/conversations/', { params: status ? { status_filter: status } : {} })

/** 创建会话 */
export const createConversation = (data) => api.post('/api/conversations/', data)

/** 获取会话详情（含消息） */
export const getConversation = (id) => api.get(`/api/conversations/${id}`)

/** 发送消息 */
export const sendMessage = (conversationId, data) =>
  api.post(`/api/conversations/${conversationId}/messages`, data)

/** 手动触发 AI 建议 */
export const triggerAiSuggest = (conversationId) =>
  api.post(`/api/conversations/${conversationId}/ai-suggest`)

/** 采纳 AI 建议（可传入编辑后内容） */
export const acceptSuggestion = (conversationId, suggestionId, content) =>
  api.post(`/api/conversations/${conversationId}/suggestions/${suggestionId}/accept`, { content })

/** 忽略 AI 建议 */
export const rejectSuggestion = (conversationId, suggestionId) =>
  api.post(`/api/conversations/${conversationId}/suggestions/${suggestionId}/reject`)

/** 关闭会话 */
export const closeConversation = (id) =>
  api.post(`/api/conversations/${id}/close`)
