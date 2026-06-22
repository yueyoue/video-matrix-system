import api from './request'

// 获取AI配置
export function getAiConfig() {
  return api.get('/ai/config')
}

// 更新AI配置
export function updateAiConfig(data) {
  return api.put('/ai/config', data)
}

// 测试AI接口
export function testAiConnection() {
  return api.post('/ai/test')
}

// 获取音色列表
export function getVoices() {
  return api.get('/ai/voices')
}

// 添加音色
export function createVoice(data) {
  return api.post('/ai/voices', data)
}

// 更新音色
export function updateVoice(id, data) {
  return api.put(`/ai/voices/${id}`, data)
}

// 删除音色
export function deleteVoice(id) {
  return api.delete(`/ai/voices/${id}`)
}
