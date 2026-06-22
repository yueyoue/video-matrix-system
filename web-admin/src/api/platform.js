import api from './request'

// 获取平台配置
export function getPlatformConfig(platform) {
  return api.get(`/platform-config/${platform}`)
}

// 更新平台配置
export function updatePlatformConfig(platform, data) {
  return api.put(`/platform-config/${platform}`, data)
}

// 恢复默认配置
export function resetPlatformConfig(platform) {
  return api.post(`/platform-config/${platform}/reset`)
}
