import axios from 'axios'

const publicApi = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '',
  timeout: 30000,
})

/** 买家端公开对话 */
export const publicChat = (message, conversationId) =>
  publicApi.post('/api/public/chat', {
    message,
    conversation_id: conversationId || undefined,
    customer_name: '访客',
  })
