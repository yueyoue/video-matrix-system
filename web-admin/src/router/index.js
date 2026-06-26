import { createRouter, createWebHashHistory } from 'vue-router'

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue')
  },
  {
    path: '/',
    component: () => import('../views/Layout.vue'),
    redirect: '/statistics',
    children: [
      { path: 'statistics', name: 'Statistics', component: () => import('../views/Statistics.vue'), meta: { title: '数据总览' } },
      { path: 'data-stats', name: 'DataStats', component: () => import('../views/DataStats.vue'), meta: { title: '数据统计' } },
      { path: 'users', name: 'UserManage', component: () => import('../views/UserManage.vue'), meta: { title: '用户管理' } },
      { path: 'ai-config', name: 'AiConfig', component: () => import('../views/AiConfig.vue'), meta: { title: 'AI配音配置' } },
      { path: 'platform-config', name: 'PlatformConfig', component: () => import('../views/PlatformConfig.vue'), meta: { title: '平台接口配置' } },
      { path: 'versions', name: 'VersionManage', component: () => import('../views/VersionManage.vue'), meta: { title: '版本管理' } },
      { path: 'logs', name: 'SystemLog', component: () => import('../views/SystemLog.vue'), meta: { title: '系统日志' } },
    ]
  }
]

const router = createRouter({
  history: createWebHashHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = localStorage.getItem('token')
  if (to.path !== '/login' && !token) {
    next('/login')
  } else if (to.path === '/login' && token) {
    next('/')
  } else {
    next()
  }
})

export default router
