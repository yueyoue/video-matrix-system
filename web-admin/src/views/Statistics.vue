<template>
  <div>
    <!-- 总数据卡片 -->
    <div class="grid grid-cols-4 gap-5 mb-6">
      <div v-for="card in statCards" :key="card.label" class="stat-card">
        <div class="flex items-center justify-between mb-3">
          <span class="text-sm text-gray-500">{{ card.label }}</span>
          <div :class="['w-9 h-9 rounded-lg flex items-center justify-center', card.bgColor]">
            <i :class="[card.icon, card.iconColor]"></i>
          </div>
        </div>
        <div class="text-2xl font-bold text-gray-900">
          <span v-if="loading" class="inline-block w-16 h-7 bg-gray-100 rounded animate-pulse"></span>
          <span v-else>{{ card.value }}</span>
        </div>
      </div>
    </div>

    <!-- 两个表格 -->
    <div class="grid grid-cols-2 gap-5">
      <!-- 用户工作量排行 -->
      <div class="table-container">
        <div class="px-4 py-3 border-b border-border flex items-center justify-between">
          <h3 class="text-sm font-semibold text-gray-900">用户工作量排行</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>排名</th>
              <th>用户名</th>
              <th>生成视频</th>
              <th>发布成功</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" v-for="i in 5" :key="i">
              <td><div class="w-6 h-4 bg-gray-100 rounded animate-pulse"></div></td>
              <td><div class="w-20 h-4 bg-gray-100 rounded animate-pulse"></div></td>
              <td><div class="w-12 h-4 bg-gray-100 rounded animate-pulse"></div></td>
              <td><div class="w-12 h-4 bg-gray-100 rounded animate-pulse"></div></td>
            </tr>
            <tr v-else-if="userStats.length === 0">
              <td colspan="4" class="text-center text-gray-400 py-8">暂无数据</td>
            </tr>
            <tr v-else v-for="(item, idx) in userStats" :key="item.username">
              <td>
                <span :class="['badge', idx < 3 ? 'badge-orange' : 'badge-gray']">{{ idx + 1 }}</span>
              </td>
              <td>{{ item.username }}</td>
              <td>{{ item.today_videos ?? item.videoCount ?? 0 }}</td>
              <td>{{ item.publish_success ?? item.publishSuccess ?? 0 }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 平台账号发布统计 -->
      <div class="table-container">
        <div class="px-4 py-3 border-b border-border flex items-center justify-between">
          <h3 class="text-sm font-semibold text-gray-900">平台账号发布统计</h3>
        </div>
        <table>
          <thead>
            <tr>
              <th>平台</th>
              <th>账号数</th>
              <th>今日发布</th>
              <th>成功率</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" v-for="i in 4" :key="i">
              <td><div class="w-16 h-4 bg-gray-100 rounded animate-pulse"></div></td>
              <td><div class="w-8 h-4 bg-gray-100 rounded animate-pulse"></div></td>
              <td><div class="w-12 h-4 bg-gray-100 rounded animate-pulse"></div></td>
              <td><div class="w-16 h-4 bg-gray-100 rounded animate-pulse"></div></td>
            </tr>
            <tr v-else-if="platformStats.length === 0">
              <td colspan="4" class="text-center text-gray-400 py-8">暂无数据</td>
            </tr>
            <tr v-else v-for="item in platformStats" :key="item.platform">
              <td>{{ item.platform }}</td>
              <td>{{ item.accounts ?? item.accountCount ?? 0 }}</td>
              <td>{{ item.today_publish ?? item.publishCount ?? 0 }}</td>
              <td>
                <span :class="(item.success_rate ?? item.successRate ?? 0) >= 90 ? 'text-success' : (item.success_rate ?? item.successRate ?? 0) >= 70 ? 'text-warning' : 'text-danger'">
                  {{ item.success_rate ?? item.successRate ?? 0 }}%
                </span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { getStatsOverview, getStatsUsers, getStatsPlatforms } from '../api/stats'

const loading = ref(true)
const statCards = reactive([
  { label: '总用户数', value: 0, icon: 'fas fa-users', bgColor: 'bg-blue-50', iconColor: 'text-primary' },
  { label: '今日生成视频', value: 0, icon: 'fas fa-video', bgColor: 'bg-green-50', iconColor: 'text-success' },
  { label: '今日发布成功', value: 0, icon: 'fas fa-check-circle', bgColor: 'bg-orange-50', iconColor: 'text-warning' },
  { label: '今日发布失败', value: 0, icon: 'fas fa-times-circle', bgColor: 'bg-red-50', iconColor: 'text-danger' },
])
const userStats = ref([])
const platformStats = ref([])

async function fetchData() {
  loading.value = true
  try {
    const [overview, users, platforms] = await Promise.all([
      getStatsOverview(),
      getStatsUsers(),
      getStatsPlatforms()
    ])
    const od = overview.data || {}
    statCards[0].value = od.total_users ?? od.totalUsers ?? 0
    statCards[1].value = od.today_videos ?? od.todayVideos ?? 0
    statCards[2].value = od.today_publish_success ?? od.todaySuccess ?? 0
    statCards[3].value = od.today_publish_failed ?? od.todayFailed ?? 0
    const ud = users.data || {}
    userStats.value = Array.isArray(ud) ? ud : (ud.list || [])
    platformStats.value = platforms.data || []
  } catch (e) {
    console.error('获取统计数据失败:', e)
  } finally {
    loading.value = false
  }
}

onMounted(fetchData)
</script>
