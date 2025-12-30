import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * 发送聊天消息
 * @param {string} message - 用户消息
 * @param {Array} history - 对话历史
 * @returns {Promise} API响应
 */
export async function sendMessage(message, history = []) {
  try {
    const response = await api.post('/api/chat', {
      message,
      history: history.map(msg => ({
        role: msg.role,
        content: msg.content
      }))
    })
    return response.data
  } catch (error) {
    console.error('API调用失败:', error)
    throw error
  }
}

/**
 * 健康检查
 * @returns {Promise} API响应
 */
export async function healthCheck() {
  try {
    const response = await api.get('/api/health')
    return response.data
  } catch (error) {
    console.error('健康检查失败:', error)
    throw error
  }
}

export default api

