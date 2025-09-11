// src/api/index.ts
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    // 可以在这里添加认证token等
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error('API Error:', error)

    // 统一错误处理
    if (error.response?.status === 401) {
      // 处理认证错误
      console.error('认证错误')
    } else if (error.response?.status >= 500) {
      // 处理服务器错误
      console.error('服务器错误')
    }

    return Promise.reject(error)
  }
)

export default api