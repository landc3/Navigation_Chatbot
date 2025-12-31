import axios from 'axios'

// 使用相对路径，通过Vite代理转发到后端
// 开发环境：通过Vite代理到 http://localhost:8000
// 生产环境：可以设置 VITE_API_BASE_URL 环境变量
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30秒超时
})

// 请求拦截器 - 添加调试信息
api.interceptors.request.use(
  (config) => {
    console.log('API请求:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(error)
  }
)

// 响应拦截器 - 统一错误处理
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    if (error.response) {
      // 服务器返回了错误状态码
      console.error('API错误响应:', error.response.status, error.response.data)
    } else if (error.request) {
      // 请求已发出但没有收到响应
      console.error('API请求失败: 无响应', error.request)
    } else {
      // 其他错误
      console.error('API错误:', error.message)
    }
    return Promise.reject(error)
  }
)

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

