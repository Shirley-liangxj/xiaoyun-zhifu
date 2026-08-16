import api from './client'

export const listQuickReplies = (category) =>
  api.get('/api/quick-replies/', { params: category ? { category } : {} })

export const createQuickReply = (data) => api.post('/api/quick-replies/', data)
export const updateQuickReply = (id, data) => api.put(`/api/quick-replies/${id}`, data)
export const deleteQuickReply = (id) => api.delete(`/api/quick-replies/${id}`)
export const useQuickReply = (id) => api.post(`/api/quick-replies/${id}/use`)
