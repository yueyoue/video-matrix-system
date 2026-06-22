import api from './request'

// 获取统计数据概览
export function getStatsOverview() {
  return api.get('/stats/overview')
}

// 获取用户工作量排行
export function getStatsUsers() {
  return api.get('/stats/users')
}

// 获取平台账号发布统计
export function getStatsPlatforms() {
  return api.get('/stats/platforms')
}
