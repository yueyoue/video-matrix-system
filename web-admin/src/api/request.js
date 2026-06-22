import axios from 'axios'
import router from '../router'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

// 请求拦截器 - 添加 Token
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}, error => Promise.reject(error))

// 响应拦截器 - 统一处理
api.interceptors.response.use(
  response => {
    const { data } = response
    if (data.code !== 0) {
      const error = new Error(data.message || '请求失败')
      error.code = data.code
      return Promise.reject(error)
    }
    return data
  },
  error => {
    if (error.response) {
      const { status, data } = error.response
      if (status === 401) {
        localStorage.removeItem('token')
        localStorage.removeItem('user')
        router.push('/login')
      }
      const msg = data?.message || `请求失败 (${status})`
      return Promise.reject(new Error(msg))
    }
    return Promise.reject(error)
  }
)

export default api
