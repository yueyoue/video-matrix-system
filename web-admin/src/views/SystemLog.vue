<template>
  <div>
    <!-- 筛选栏 -->
    <div class="bg-white rounded-card shadow-card p-4 mb-5 flex items-center gap-4">
      <div class="flex items-center gap-2">
        <label class="text-sm text-gray-500">日志级别</label>
        <select v-model="filters.level" class="form-select w-32">
          <option value="">全部</option>
          <option value="info">INFO</option>
          <option value="warn">WARN</option>
          <option value="error">ERROR</option>
          <option value="debug">DEBUG</option>
        </select>
      </div>
      <div class="flex items-center gap-2 flex-1 max-w-xs">
        <label class="text-sm text-gray-500">关键词</label>
        <input v-model="filters.keyword" class="form-input" placeholder="搜索日志内容..." @keyup.enter="fetchLogs" />
      </div>
      <button class="btn-default" @click="fetchLogs">
        <i class="fas fa-search"></i> 搜索
      </button>
      <button class="btn-default" @click="handleExport">
        <i class="fas fa-download"></i> 导出
      </button>
    </div>

    <!-- 日志表格 -->
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th style="width: 160px">时间</th>
            <th style="width: 80px">级别</th>
            <th style="width: 100px">用户</th>
            <th style="width: 160px">操作</th>
            <th>详情</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading" v-for="i in 8" :key="i">
            <td v-for="j in 5" :key="j"><div class="h-4 bg-gray-100 rounded animate-pulse" :style="{ width: j === 5 ? '200px' : '80px' }"></div></td>
          </tr>
          <tr v-else-if="logs.length === 0">
            <td colspan="5" class="text-center text-gray-400 py-8">暂无日志</td>
          </tr>
          <tr v-else v-for="log in logs" :key="log.id">
            <td class="text-xs text-gray-400">{{ log.timestamp }}</td>
            <td>
              <span :class="['badge', levelClass(log.level)]">{{ log.level?.toUpperCase() }}</span>
            </td>
            <td>{{ log.username || '-' }}</td>
            <td>{{ log.action }}</td>
            <td class="text-gray-500 text-xs max-w-md truncate">{{ log.detail }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, inject } from 'vue'
import { getLogs, exportLogs } from '../api/logs'

const showToast = inject('showToast')
const loading = ref(true)
const logs = ref([])
const filters = reactive({ level: '', keyword: '' })

function levelClass(level) {
  const map = { info: 'badge-blue', warn: 'badge-orange', error: 'badge-red', debug: 'badge-gray' }
  return map[level] || 'badge-gray'
}

async function fetchLogs() {
  loading.value = true
  try {
    const params = {}
    if (filters.level) params.level = filters.level
    if (filters.keyword) params.keyword = filters.keyword
    const res = await getLogs(params)
    logs.value = res.data || []
  } catch (e) {
    showToast(e.message || '获取日志失败', 'error')
  } finally {
    loading.value = false
  }
}

async function handleExport() {
  try {
    const params = {}
    if (filters.level) params.level = filters.level
    if (filters.keyword) params.keyword = filters.keyword
    const res = await exportLogs(params)
    const url = URL.createObjectURL(res)
    const a = document.createElement('a')
    a.href = url
    a.download = `logs-${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
    showToast('日志导出成功')
  } catch (e) {
    showToast(e.message || '导出失败', 'error')
  }
}

onMounted(fetchLogs)
</script>
