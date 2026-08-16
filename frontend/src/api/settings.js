import api from './client'

export const getSettings = () => api.get('/api/settings/')
export const updateSettings = (data) => api.put('/api/settings/', data)
export const getSystemStatus = () => api.get('/api/settings/status')
export const testApi = () => api.post('/api/settings/test-api')
export const reindexKnowledge = () => api.post('/api/settings/reindex')
export const updateCompany = (company_name) => api.put('/api/settings/company', { company_name })
