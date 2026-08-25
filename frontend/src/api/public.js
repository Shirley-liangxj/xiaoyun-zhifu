import axios from 'axios'

const publicApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
})

function withCompany(companyId) {
  return companyId != null ? { company_id: companyId } : {}
}

export const getPublicConfig = (companyId) =>
  publicApi.get('/api/public/config', { params: withCompany(companyId) })

export const publicChat = (message, conversationId, customerName, companyId) =>
  publicApi.post('/api/public/chat', {
    message,
    conversation_id: conversationId || undefined,
    customer_name: customerName || '访客',
    company_id: companyId || undefined,
  }, { params: withCompany(companyId) })

export const transferToHuman = (conversationId, customerName, companyId) =>
  publicApi.post('/api/public/transfer', {
    conversation_id: conversationId || undefined,
    customer_name: customerName || '访客',
    company_id: companyId || undefined,
  }, { params: withCompany(companyId) })

export const getPublicConversation = (conversationId, companyId) =>
  publicApi.get(`/api/public/conversations/${conversationId}`, {
    params: withCompany(companyId),
  })
