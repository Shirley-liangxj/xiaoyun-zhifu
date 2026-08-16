import api from './client'

/** 获取 Dashboard 统计数据 */
export const getDashboardStats = () => api.get('/api/stats/dashboard')
