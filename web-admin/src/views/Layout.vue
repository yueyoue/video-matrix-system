<template>
  <div class="flex h-screen bg-bg">
    <!-- 侧边栏 -->
    <aside class="w-60 bg-white border-r border-border flex flex-col shrink-0">
      <!-- Logo -->
      <div class="px-5 py-4 border-b border-border">
        <div class="flex items-center gap-3">
          <div class="w-9 h-9 bg-primary rounded-lg flex items-center justify-center">
            <i class="fas fa-video text-white text-sm"></i>
          </div>
          <div>
            <div class="font-semibold text-gray-900 text-sm">视频矩阵系统</div>
            <div class="text-xs text-gray-400">管理后台</div>
          </div>
        </div>
      </div>

      <!-- 导航菜单 -->
      <nav class="flex-1 py-3 px-3 overflow-y-auto">
        <router-link
          v-for="item in menuItems"
          :key="item.path"
          :to="item.path"
          :class="[
            'flex items-center gap-3 px-3 py-2.5 rounded-btn text-sm mb-0.5 transition-colors',
            isActive(item.path)
              ? 'bg-primary/10 text-primary font-medium'
              : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
          ]"
        >
          <i :class="item.icon" class="w-5 text-center text-sm"></i>
          {{ item.label }}
        </router-link>
      </nav>

      <!-- 底部用户信息 -->
      <div class="px-4 py-3 border-t border-border">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center">
            <i class="fas fa-user text-gray-500 text-xs"></i>
          </div>
          <div class="flex-1 min-w-0">
            <div class="text-sm font-medium text-gray-900 truncate">{{ userStore.user?.username || '管理员' }}</div>
            <div class="text-xs text-gray-400">{{ userStore.user?.role === 'admin' ? '超级管理员' : '普通用户' }}</div>
          </div>
          <button @click="handleLogout" class="text-gray-400 hover:text-danger transition-colors" title="退出登录">
            <i class="fas fa-sign-out-alt text-sm"></i>
          </button>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <div class="flex-1 flex flex-col min-w-0">
      <!-- 顶部栏 -->
      <header class="h-14 bg-white border-b border-border flex items-center justify-between px-6 shrink-0">
        <div class="flex items-center gap-3">
          <h2 class="text-base font-semibold text-gray-900">{{ currentTitle }}</h2>
        </div>
        <div class="flex items-center gap-4">
          <span class="text-sm text-gray-500">
            <i class="far fa-calendar-alt mr-1.5"></i>{{ currentDate }}
          </span>
          <button @click="handleRefresh" class="text-gray-400 hover:text-primary transition-colors" title="刷新">
            <i class="fas fa-sync-alt text-sm"></i>
          </button>
        </div>
      </header>

      <!-- 页面内容 -->
      <main class="flex-1 overflow-y-auto p-6">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" :key="$route.path" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, inject } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useUserStore } from '../stores/user'

const route = useRoute()
const router = useRouter()
const userStore = useUserStore()
const showToast = inject('showToast')

const menuItems = [
  { path: '/statistics', label: '数据统计', icon: 'fas fa-chart-bar' },
  { path: '/users', label: '用户管理', icon: 'fas fa-users' },
  { path: '/ai-config', label: 'AI配音配置', icon: 'fas fa-microphone' },
  { path: '/platform-config', label: '平台接口配置', icon: 'fas fa-cogs' },
  { path: '/versions', label: '版本管理', icon: 'fas fa-box' },
  { path: '/logs', label: '系统日志', icon: 'fas fa-file-alt' },
]

const currentTitle = computed(() => route.meta?.title || '数据统计')

const currentDate = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
})

function isActive(path) {
  return route.path === path
}

function handleRefresh() {
  router.replace({ path: '/redirect' + route.path })
  // 简单刷新方式
  window.location.reload()
}

function handleLogout() {
  userStore.logout()
  router.push('/login')
  showToast('已退出登录')
}
</script>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.15s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
