<template>
  <div class="min-h-screen bg-bg flex items-center justify-center">
    <div class="w-full max-w-sm mx-4">
      <!-- Logo -->
      <div class="text-center mb-8">
        <div class="w-16 h-16 bg-primary rounded-2xl flex items-center justify-center mx-auto mb-4">
          <i class="fas fa-video text-white text-2xl"></i>
        </div>
        <h1 class="text-2xl font-bold text-gray-900">视频矩阵系统</h1>
        <p class="text-gray-500 text-sm mt-1">管理后台</p>
      </div>

      <!-- 登录表单 -->
      <div class="bg-white rounded-card shadow-card p-6">
        <form @submit.prevent="handleLogin">
          <div class="form-group">
            <label class="form-label">用户名</label>
            <div class="relative">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                <i class="fas fa-user text-sm"></i>
              </span>
              <input
                v-model="form.username"
                type="text"
                class="form-input pl-9"
                placeholder="请输入用户名"
                autocomplete="username"
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">密码</label>
            <div class="relative">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                <i class="fas fa-lock text-sm"></i>
              </span>
              <input
                v-model="form.password"
                type="password"
                class="form-input pl-9"
                placeholder="请输入密码"
                autocomplete="current-password"
              />
            </div>
          </div>

          <div v-if="error" class="mb-4 text-sm text-danger flex items-center gap-1.5">
            <i class="fas fa-exclamation-circle"></i>
            {{ error }}
          </div>

          <button
            type="submit"
            class="btn-primary w-full justify-center py-2.5"
            :disabled="loading"
          >
            <span v-if="loading" class="loading-spinner"></span>
            <span v-else>登 录</span>
          </button>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref, inject } from 'vue'
import { useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'

const router = useRouter()
const userStore = useUserStore()
const showToast = inject('showToast')

const form = reactive({ username: '', password: '' })
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  if (!form.username || !form.password) {
    error.value = '请输入用户名和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await userStore.login(form.username, form.password)
    showToast('登录成功')
    router.push('/')
  } catch (e) {
    error.value = e.message || '登录失败'
  } finally {
    loading.value = false
  }
}
</script>
