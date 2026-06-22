import api from './request'

// 获取用户列表
export function getUsers(params) {
  return api.get('/users', { params })
}

// 创建用户
export function createUser(data) {
  return api.post('/users', data)
}

// 更新用户
export function updateUser(id, data) {
  return api.put(`/users/${id}`, data)
}

// 删除用户
export function deleteUser(id) {
  return api.delete(`/users/${id}`)
}

// 切换用户状态
export function toggleUserStatus(id, data) {
  return api.put(`/users/${id}`, data)
}
