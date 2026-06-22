import api from './request'

// 获取日志列表
export function getLogs(params) {
  return api.get('/logs', { params })
}

// 导出日志
export function exportLogs(params) {
  return api.get('/logs/export', { params, responseType: 'blob' })
}
