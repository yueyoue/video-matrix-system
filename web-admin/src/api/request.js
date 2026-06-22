import axios from 'axios'
import router from '../router'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' }
})

// 请求拦截器 - 添加 Token 和 .php 后缀
api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  // 自动添加 .php 后缀，避免依赖 nginx URL 重写
  // /auth/login → /auth/login.php
  // /users/5    → /users.php/5
  // /ai/config  → /ai/config.php
  if (config.url && !config.url.endsWith('.php')) {
    let url = config.url
    let query = ''
    const qi = url.indexOf('?')
    if (qi !== -1) { query = url.slice(qi); url = url.slice(0, qi) }
    const parts = url.split('/').filter(Boolean)
    if (parts.length === 1) {
      // /users → /users.php
      config.url = '/' + parts[0].replace(/-/g, '_') + '.php' + query
    } else if (parts.length >= 2) {
      const first = parts[0].replace(/-/g, '_')
      const rest = parts.slice(1)
      if (['auth', 'ai'].includes(first)) {
        // 子目录结构: auth/login.php, ai/config.php
        config.url = '/' + first + '/' + rest.join('/') + '.php' + query
      } else {
        // 扁平结构用子路径做路由: users.php/5, platform_config.php/douyin
        // 通过 _r 查询参数传递子路由
        const sep = query ? '&' : '?'
        config.url = '/' + first + '.php' + query + sep + '_r=' + rest.join('/')
      }
    }
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
