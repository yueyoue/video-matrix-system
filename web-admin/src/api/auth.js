import api from './request'

// 登录
export function login(data) {
  return api.post('/auth/login', data)
}

// 获取当前用户信息
export function getUserInfo() {
  return api.get('/auth/profile')
}
