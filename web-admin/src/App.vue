<template>
  <div v-if="globalError" class="fixed inset-0 z-50 bg-white flex items-center justify-center p-8">
    <div class="max-w-2xl w-full">
      <div class="flex items-center gap-3 mb-4">
        <span class="text-3xl">⚠️</span>
        <h1 class="text-xl font-bold text-red-600">页面加载出错</h1>
      </div>
      <div class="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
        <pre class="text-sm text-red-800 whitespace-pre-wrap break-all">{{ globalError }}</pre>
      </div>
      <div class="text-sm text-gray-500 mb-4">
        <p>服务器地址: {{ apiBase }}</p>
        <p>Token: {{ hasToken ? '已保存' : '未保存' }}</p>
        <p>当前路径: {{ currentPath }}</p>
      </div>
      <button @click="clearAndReload" class="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600">
        清除缓存并重新登录
      </button>
    </div>
  </div>
  <router-view v-else />
  <div v-if="toast.show" :class="['toast', `toast-${toast.type}`]">
    <i :class="toastIcon" class="mr-2"></i>
    {{ toast.message }}
  </div>
</template>

<script setup>
import { reactive, computed, provide, ref, onErrorCaptured } from 'vue'

const globalError = ref('')
const apiBase = ref('/api')
const hasToken = ref(!!localStorage.getItem('token'))
const currentPath = ref(window.location.hash)

// 全局 Vue 错误捕获
onErrorCaptured((err, instance, info) => {
  globalError.value = `[Vue Error] ${err.message}\n\nInfo: ${info}\n\nStack: ${err.stack}`
  return false // 阻止错误继续传播
})

// 全局 JS 错误捕获
window.addEventListener('error', (event) => {
  if (!globalError.value) {
    globalError.value = `[JS Error] ${event.message}\n\nFile: ${event.filename}\nLine: ${event.lineno}\nColumn: ${event.colno}`
  }
})

// 未处理的 Promise 错误
window.addEventListener('unhandledrejection', (event) => {
  if (!globalError.value) {
    const reason = event.reason
    const msg = reason instanceof Error ? `${reason.message}\n\nStack: ${reason.stack}` : String(reason)
    globalError.value = `[API Error] ${msg}`
  }
})

function clearAndReload() {
  localStorage.clear()
  window.location.href = '/'
}

const toast = reactive({ show: false, message: '', type: 'success', timer: null })

const toastIcons = {
  success: 'fas fa-check-circle',
  error: 'fas fa-times-circle',
  warning: 'fas fa-exclamation-circle'
}

const toastIcon = computed(() => toastIcons[toast.type] || toastIcons.success)

function showToast(message, type = 'success', duration = 3000) {
  if (toast.timer) clearTimeout(toast.timer)
  toast.show = true
  toast.message = message
  toast.type = type
  toast.timer = setTimeout(() => {
    toast.show = false
  }, duration)
}

provide('showToast', showToast)
</script>
