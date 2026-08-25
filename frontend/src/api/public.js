import axios from 'axios'

const publicApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
})

export const getPublicConfig = () => publicApi.get('/api/public/config')

export const publicChat = (message, conversationId, customerName) =>
  publicApi.post('/api/public/chat', {
    message,
    conversation_id: conversationId || undefined,
    customer_name: customerName || '访客',
  })

export const transferToHuman = (conversationId, customerName) =>
  publicApi.post('/api/public/transfer', {
    conversation_id: conversationId || undefined,
    customer_name: customerName || '访客',
  })

export const getPublicConversation = (conversationId) =>
  publicApi.get(`/api/public/conversations/${conversationId}`)
