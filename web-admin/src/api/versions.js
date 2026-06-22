import api from './request'

// 获取版本列表
export function getVersions() {
  return api.get('/versions')
}

// 创建新版本
export function createVersion(data) {
  return api.post('/versions', data, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

// 更新版本状态
export function updateVersion(id, data) {
  return api.put(`/versions/${id}`, data)
}
