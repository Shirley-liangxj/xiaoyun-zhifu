import api from './client'

/** 获取工单列表 */
export const listTickets = (params) => api.get('/api/tickets/', { params })

/** 创建工单 */
export const createTicket = (data) => api.post('/api/tickets/', data)

/** 获取工单详情 */
export const getTicket = (id) => api.get(`/api/tickets/${id}`)

/** 更新工单 */
export const updateTicket = (id, data) => api.put(`/api/tickets/${id}`, data)

/** 删除工单 */
export const deleteTicket = (id) => api.delete(`/api/tickets/${id}`)
