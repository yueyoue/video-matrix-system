import api from './request'

// 监控账号 CRUD
export function getMonitoredAccounts(params = {}) {
  return api.get('/accounts-data', { params })
}

export function addMonitoredAccount(data) {
  return api.post('/accounts-data', data)
}

export function updateMonitoredAccount(id, data) {
  return api.put(`/accounts-data/${id}`, data)
}

export function deleteMonitoredAccount(id) {
  return api.delete(`/accounts-data/${id}`)
}

// 数据同步
export function syncData(accountId = 0) {
  return api.post('/accounts-data/sync', { account_id: accountId })
}

// 视频数据列表
export function getVideoData(params = {}) {
  return api.get('/accounts-data/videos', { params })
}

// 汇总统计
export function getDataSummary(params = {}) {
  return api.get('/accounts-data/summary', { params })
}

// 导出URL构建
export function buildExportUrl(params = {}) {
  const token = localStorage.getItem('token')
  const base = '/api/accounts-data/export'
  const query = new URLSearchParams()
  if (params.platform) query.set('platform', params.platform)
  if (params.account_name) query.set('account_name', params.account_name)
  if (params.startDate) query.set('startDate', params.startDate)
  if (params.endDate) query.set('endDate', params.endDate)
  const qs = query.toString()
  return `${base}${qs ? '?' + qs : ''}`
}
