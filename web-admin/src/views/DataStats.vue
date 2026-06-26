<template>
  <div>
    <!-- 筛选栏 -->
    <div class="bg-white rounded-lg border border-border p-4 mb-5">
      <div class="flex flex-wrap items-center gap-3">
        <select v-model="filters.platform" class="input-select" @change="loadData">
          <option value="">全部平台</option>
          <option value="douyin">抖音</option>
          <option value="kuaishou">快手</option>
          <option value="xiaohongshu">小红书</option>
          <option value="weixin">视频号</option>
        </select>
        <select v-model="filters.account_name" class="input-select" @change="loadData">
          <option value="">全部账号</option>
          <option v-for="a in accountOptions" :key="a.account_name" :value="a.account_name">{{ a.account_name }}</option>
        </select>
        <input type="date" v-model="filters.startDate" class="input-select" @change="loadData" />
        <span class="text-gray-400 text-sm">至</span>
        <input type="date" v-model="filters.endDate" class="input-select" @change="loadData" />
        <div class="flex-1"></div>
        <button @click="handleSync()" :disabled="syncing" class="btn-primary">
          <i class="fas fa-sync-alt mr-1.5" :class="{ 'fa-spin': syncing }"></i>{{ syncing ? '同步中...' : '数据同步' }}
        </button>
        <button @click="handleExport" class="btn-outline">
          <i class="fas fa-file-export mr-1.5"></i>导出Excel
        </button>
      </div>
    </div>

    <!-- 汇总卡片 -->
    <div class="grid grid-cols-5 gap-4 mb-5">
      <div v-for="card in summaryCards" :key="card.label" class="stat-card">
        <div class="flex items-center justify-between mb-2">
          <span class="text-xs text-gray-500">{{ card.label }}</span>
          <div :class="['w-8 h-8 rounded-lg flex items-center justify-center', card.bgColor]">
            <i :class="[card.icon, card.iconColor, 'text-xs']"></i>
          </div>
        </div>
        <div class="text-xl font-bold text-gray-900">
          <span v-if="loading" class="inline-block w-14 h-6 bg-gray-100 rounded animate-pulse"></span>
          <span v-else>{{ formatNumber(card.value) }}</span>
        </div>
      </div>
    </div>

    <!-- Tab 切换 -->
    <div class="flex gap-1 mb-4 border-b border-border">
      <button v-for="tab in tabs" :key="tab.key" @click="activeTab = tab.key"
        :class="['px-4 py-2.5 text-sm font-medium border-b-2 transition-colors', activeTab === tab.key ? 'border-primary text-primary' : 'border-transparent text-gray-500 hover:text-gray-700']">
        {{ tab.label }}
      </button>
    </div>

    <!-- Tab: 监控账号管理 -->
    <div v-if="activeTab === 'accounts'">
      <div class="flex items-center justify-between mb-4">
        <div class="text-sm text-gray-500">共 {{ accountsList.length }} 个监控账号</div>
        <button @click="showAddDialog = true" class="btn-primary text-sm">
          <i class="fas fa-plus mr-1.5"></i>添加账号
        </button>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th style="width:50px">ID</th>
              <th style="width:80px">平台</th>
              <th>账号名称</th>
              <th style="width:80px">视频数</th>
              <th style="width:100px">总播放</th>
              <th style="width:100px">总点赞</th>
              <th style="width:100px">总评论</th>
              <th style="width:100px">总分享</th>
              <th style="width:150px">最后同步</th>
              <th style="width:80px">状态</th>
              <th style="width:160px">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="accountsLoading" v-for="i in 5" :key="i">
              <td v-for="j in 11" :key="j"><div class="h-4 bg-gray-100 rounded animate-pulse"></div></td>
            </tr>
            <tr v-else-if="accountsList.length === 0">
              <td colspan="11" class="text-center text-gray-400 py-10">
                <i class="fas fa-inbox text-3xl mb-2 block text-gray-300"></i>
                暂无监控账号，点击「添加账号」开始
              </td>
            </tr>
            <tr v-else v-for="item in accountsList" :key="item.id">
              <td class="text-gray-400">{{ item.id }}</td>
              <td><span :class="platformBadgeClass(item.platform)">{{ platformName(item.platform) }}</span></td>
              <td class="font-medium">{{ item.account_name }}</td>
              <td>{{ item.total_videos }}</td>
              <td>{{ formatNumber(item.total_plays) }}</td>
              <td>{{ formatNumber(item.total_likes) }}</td>
              <td>{{ formatNumber(item.total_comments) }}</td>
              <td>{{ formatNumber(item.total_shares) }}</td>
              <td class="text-gray-400 text-xs">{{ item.last_sync || '从未同步' }}</td>
              <td>
                <span :class="item.status === 'active' ? 'badge badge-green' : 'badge badge-red'">
                  {{ item.status === 'active' ? '正常' : '异常' }}
                </span>
              </td>
              <td>
                <div class="flex gap-1">
                  <button @click="handleSyncOne(item.id)" class="btn-text text-xs" :disabled="syncing">
                    <i class="fas fa-sync-alt mr-0.5"></i>同步
                  </button>
                  <button @click="editAccount(item)" class="btn-text text-xs">
                    <i class="fas fa-edit mr-0.5"></i>编辑
                  </button>
                  <button @click="deleteAccount(item)" class="btn-text text-xs text-danger">
                    <i class="fas fa-trash mr-0.5"></i>删除
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Tab: 平台统计 -->
    <div v-if="activeTab === 'platforms'">
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>平台</th>
              <th>视频数</th>
              <th>总播放量</th>
              <th>总点赞量</th>
              <th>总评论量</th>
              <th>总分享量</th>
              <th>平均播放量</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading" v-for="i in 4" :key="i">
              <td v-for="j in 7" :key="j"><div class="h-4 bg-gray-100 rounded animate-pulse"></div></td>
            </tr>
            <tr v-else-if="platformData.length === 0">
              <td colspan="7" class="text-center text-gray-400 py-10">暂无数据</td>
            </tr>
            <tr v-else v-for="item in platformData" :key="item.platform">
              <td><span :class="platformBadgeClass(item.platform)">{{ platformName(item.platform) }}</span></td>
              <td>{{ item.video_count }}</td>
              <td class="font-medium">{{ formatNumber(item.plays) }}</td>
              <td>{{ formatNumber(item.likes) }}</td>
              <td>{{ formatNumber(item.comments) }}</td>
              <td>{{ formatNumber(item.shares) }}</td>
              <td>{{ item.video_count > 0 ? formatNumber(Math.round(item.plays / item.video_count)) : 0 }}</td>
            </tr>
            <!-- 合计行 -->
            <tr v-if="platformData.length > 0" class="bg-gray-50 font-semibold">
              <td>合计</td>
              <td>{{ platformData.reduce((s, p) => s + p.video_count, 0) }}</td>
              <td>{{ formatNumber(platformData.reduce((s, p) => s + p.plays, 0)) }}</td>
              <td>{{ formatNumber(platformData.reduce((s, p) => s + p.likes, 0)) }}</td>
              <td>{{ formatNumber(platformData.reduce((s, p) => s + p.comments, 0)) }}</td>
              <td>{{ formatNumber(platformData.reduce((s, p) => s + p.shares, 0)) }}</td>
              <td>-</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 账号排行 -->
      <div class="mt-5">
        <h3 class="text-sm font-semibold text-gray-900 mb-3">账号播放量排行</h3>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th style="width:50px">排名</th>
                <th>平台</th>
                <th>账号</th>
                <th>视频数</th>
                <th>播放量</th>
                <th>点赞量</th>
                <th>评论量</th>
                <th>分享量</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="accountRankData.length === 0">
                <td colspan="8" class="text-center text-gray-400 py-8">暂无数据</td>
              </tr>
              <tr v-else v-for="(item, idx) in accountRankData" :key="item.account_name">
                <td><span :class="['badge', idx < 3 ? 'badge-orange' : 'badge-gray']">{{ idx + 1 }}</span></td>
                <td><span :class="platformBadgeClass(item.platform)">{{ platformName(item.platform) }}</span></td>
                <td class="font-medium">{{ item.account_name }}</td>
                <td>{{ item.video_count }}</td>
                <td class="font-medium">{{ formatNumber(item.plays) }}</td>
                <td>{{ formatNumber(item.likes) }}</td>
                <td>{{ formatNumber(item.comments) }}</td>
                <td>{{ formatNumber(item.shares) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Tab: 视频明细 -->
    <div v-if="activeTab === 'videos'">
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>平台</th>
              <th>账号</th>
              <th>视频标题</th>
              <th style="width:90px">播放量</th>
              <th style="width:80px">点赞量</th>
              <th style="width:80px">评论量</th>
              <th style="width:80px">分享量</th>
              <th style="width:150px">发布时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="videoLoading" v-for="i in 10" :key="i">
              <td v-for="j in 8" :key="j"><div class="h-4 bg-gray-100 rounded animate-pulse"></div></td>
            </tr>
            <tr v-else-if="videoList.length === 0">
              <td colspan="8" class="text-center text-gray-400 py-10">
                <i class="fas fa-video text-3xl mb-2 block text-gray-300"></i>
                暂无视频数据
              </td>
            </tr>
            <tr v-else v-for="item in videoList" :key="item.id">
              <td><span :class="platformBadgeClass(item.platform)">{{ platformName(item.platform) }}</span></td>
              <td>{{ item.account_name }}</td>
              <td class="max-w-xs truncate" :title="item.video_title">{{ item.video_title }}</td>
              <td class="font-medium">{{ formatNumber(item.plays) }}</td>
              <td>{{ formatNumber(item.likes) }}</td>
              <td>{{ formatNumber(item.comments) }}</td>
              <td>{{ formatNumber(item.shares) }}</td>
              <td class="text-gray-400 text-xs">{{ item.publish_time }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- 分页 -->
      <div v-if="videoTotal > videoPageSize" class="flex items-center justify-between mt-4">
        <span class="text-sm text-gray-500">共 {{ videoTotal }} 条</span>
        <div class="flex gap-1">
          <button @click="videoPage > 1 && (videoPage--, loadVideos())" :disabled="videoPage <= 1" class="btn-page">上一页</button>
          <span class="px-3 py-1.5 text-sm text-gray-600">{{ videoPage }} / {{ Math.ceil(videoTotal / videoPageSize) }}</span>
          <button @click="videoPage < Math.ceil(videoTotal / videoPageSize) && (videoPage++, loadVideos())" :disabled="videoPage >= Math.ceil(videoTotal / videoPageSize)" class="btn-page">下一页</button>
        </div>
      </div>
    </div>

    <!-- 添加/编辑账号弹窗 -->
    <div v-if="showAddDialog" class="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg shadow-xl w-[480px] max-h-[90vh] overflow-y-auto">
        <div class="px-5 py-4 border-b border-border">
          <h3 class="text-base font-semibold text-gray-900">{{ editingId ? '编辑监控账号' : '添加监控账号' }}</h3>
        </div>
        <div class="p-5 space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">平台 <span class="text-danger">*</span></label>
            <select v-model="addForm.platform" class="input-select w-full" :disabled="!!editingId">
              <option value="">请选择平台</option>
              <option value="douyin">抖音</option>
              <option value="kuaishou">快手</option>
              <option value="xiaohongshu">小红书</option>
              <option value="weixin">视频号</option>
            </select>
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">账号名称 <span class="text-danger">*</span></label>
            <input v-model="addForm.account_name" class="input-select w-full" placeholder="输入账号昵称/名称" />
          </div>
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1.5">主页链接</label>
            <input v-model="addForm.account_url" class="input-select w-full" placeholder="粘贴该账号的主页URL（可选，有助于精准匹配）" />
            <p class="text-xs text-gray-400 mt-1">提供主页链接可以更准确地爬取数据，不填则通过账号名称搜索</p>
          </div>
        </div>
        <div class="px-5 py-4 border-t border-border flex justify-end gap-2">
          <button @click="cancelEdit" class="btn-outline">取消</button>
          <button @click="submitAccount" :disabled="!addForm.platform || !addForm.account_name" class="btn-primary">
            {{ editingId ? '保存' : '添加' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from 'vue'
import {
  getMonitoredAccounts, addMonitoredAccount, updateMonitoredAccount, deleteMonitoredAccount,
  syncData, getVideoData, getDataSummary, buildExportUrl
} from '../api/accountsData'

const PLATFORMS = { douyin: '抖音', kuaishou: '快手', xiaohongshu: '小红书', weixin: '视频号' }
const platformName = (p) => PLATFORMS[p] || p
const platformBadgeClass = (p) => ({
  'douyin': 'badge badge-blue',
  'kuaishou': 'badge badge-orange',
  'xiaohongshu': 'badge badge-red',
  'weixin': 'badge badge-green',
}[p] || 'badge badge-gray')

// 状态
const activeTab = ref('accounts')
const loading = ref(false)
const accountsLoading = ref(false)
const videoLoading = ref(false)
const syncing = ref(false)

const tabs = [
  { key: 'accounts', label: '监控账号' },
  { key: 'platforms', label: '平台统计' },
  { key: 'videos', label: '视频明细' },
]

// 筛选
const filters = reactive({ platform: '', account_name: '', startDate: '', endDate: '' })

// 汇总数据
const summaryData = ref({ video_count: 0, plays: 0, likes: 0, comments: 0, shares: 0 })
const platformData = ref([])
const accountRankData = ref([])

const summaryCards = computed(() => [
  { label: '视频总数', value: summaryData.value.video_count, icon: 'fas fa-video', bgColor: 'bg-blue-50', iconColor: 'text-primary' },
  { label: '总播放量', value: summaryData.value.plays, icon: 'fas fa-play-circle', bgColor: 'bg-green-50', iconColor: 'text-success' },
  { label: '总点赞量', value: summaryData.value.likes, icon: 'fas fa-heart', bgColor: 'bg-red-50', iconColor: 'text-danger' },
  { label: '总评论量', value: summaryData.value.comments, icon: 'fas fa-comment', bgColor: 'bg-orange-50', iconColor: 'text-warning' },
  { label: '总分享量', value: summaryData.value.shares, icon: 'fas fa-share-alt', bgColor: 'bg-purple-50', iconColor: 'text-purple-500' },
])

// 监控账号
const accountsList = ref([])
const accountOptions = computed(() => accountsList.value)

// 视频数据
const videoList = ref([])
const videoTotal = ref(0)
const videoPage = ref(1)
const videoPageSize = 20

// 弹窗
const showAddDialog = ref(false)
const editingId = ref(0)
const addForm = reactive({ platform: '', account_name: '', account_url: '' })

function formatNumber(n) {
  if (n === null || n === undefined) return '0'
  const num = Number(n)
  if (num >= 10000) return (num / 10000).toFixed(1) + 'w'
  return num.toLocaleString()
}

// ───────────── 数据加载 ─────────────

async function loadAccounts() {
  accountsLoading.value = true
  try {
    const res = await getMonitoredAccounts()
    accountsList.value = res.data?.list || []
  } catch (e) { console.error(e) }
  finally { accountsLoading.value = false }
}

async function loadSummary() {
  loading.value = true
  try {
    const params = { ...filters }
    const res = await getDataSummary(params)
    const d = res.data || {}
    summaryData.value = d.summary || { video_count: 0, plays: 0, likes: 0, comments: 0, shares: 0 }
    platformData.value = d.platforms || []
    accountRankData.value = d.accounts || []
  } catch (e) { console.error(e) }
  finally { loading.value = false }
}

async function loadVideos() {
  videoLoading.value = true
  try {
    const params = { ...filters, page: videoPage.value, pageSize: videoPageSize }
    const res = await getVideoData(params)
    const d = res.data || {}
    videoList.value = d.list || []
    videoTotal.value = d.total || 0
  } catch (e) { console.error(e) }
  finally { videoLoading.value = false }
}

function loadData() {
  videoPage.value = 1
  loadSummary()
  loadVideos()
}

// ───────────── 操作 ─────────────

async function handleSync(accountId = 0) {
  syncing.value = true
  try {
    const res = await syncData(accountId)
    showToast(res.message || '同步完成')
    loadData()
    loadAccounts()
  } catch (e) { showToast(e.message || '同步失败', 'error') }
  finally { syncing.value = false }
}

function handleSyncOne(id) { handleSync(id) }

function handleExport() {
  const url = buildExportUrl(filters)
  const token = localStorage.getItem('token')
  // 创建隐藏链接下载
  const a = document.createElement('a')
  a.href = url + (url.includes('?') ? '&' : '?') + '_token=' + token
  a.download = 'video_data.csv'
  // 使用fetch下载以携带Authorization头
  fetch(url, { headers: { 'Authorization': 'Bearer ' + token } })
    .then(r => r.blob())
    .then(blob => {
      const blobUrl = URL.createObjectURL(blob)
      a.href = blobUrl
      a.click()
      URL.revokeObjectURL(blobUrl)
    })
    .catch(() => showToast('导出失败', 'error'))
}

// 账号 CRUD
function editAccount(item) {
  editingId.value = item.id
  addForm.platform = item.platform
  addForm.account_name = item.account_name
  addForm.account_url = item.account_url || ''
  showAddDialog.value = true
}

function cancelEdit() {
  showAddDialog.value = false
  editingId.value = 0
  addForm.platform = ''
  addForm.account_name = ''
  addForm.account_url = ''
}

async function submitAccount() {
  try {
    if (editingId.value) {
      await updateMonitoredAccount(editingId.value, { account_name: addForm.account_name, account_url: addForm.account_url })
      showToast('更新成功')
    } else {
      await addMonitoredAccount({ platform: addForm.platform, account_name: addForm.account_name, account_url: addForm.account_url })
      showToast('添加成功')
    }
    cancelEdit()
    loadAccounts()
  } catch (e) { showToast(e.message || '操作失败', 'error') }
}

async function deleteAccount(item) {
  if (!confirm(`确定删除监控账号「${item.account_name}」？\n该账号的视频数据也会一并删除。`)) return
  try {
    await deleteMonitoredAccount(item.id)
    showToast('已删除')
    loadAccounts()
    loadData()
  } catch (e) { showToast(e.message || '删除失败', 'error') }
}

// 注入 toast
const showToast = inject('showToast', (msg) => alert(msg))

onMounted(() => {
  loadAccounts()
  // 默认加载近30天数据
  const now = new Date()
  const end = now.toISOString().split('T')[0]
  const start = new Date(now.getTime() - 30 * 86400000).toISOString().split('T')[0]
  filters.startDate = start
  filters.endDate = end
  loadData()
})
</script>

<script>
import { inject } from 'vue'
export default { name: 'DataStats' }
</script>

<style scoped>
.input-select {
  @apply h-9 px-3 text-sm border border-border rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary;
}
.btn-primary {
  @apply h-9 px-4 text-sm font-medium text-white bg-primary rounded-lg hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed;
}
.btn-outline {
  @apply h-9 px-4 text-sm font-medium text-gray-700 bg-white border border-border rounded-lg hover:bg-gray-50 transition-colors;
}
.btn-text {
  @apply px-2 py-1 text-xs text-primary hover:bg-primary/10 rounded transition-colors disabled:opacity-50;
}
.btn-page {
  @apply px-3 py-1.5 text-sm border border-border rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed;
}
.badge { @apply inline-block px-2 py-0.5 text-xs font-medium rounded-full; }
.badge-blue { @apply bg-blue-50 text-blue-600; }
.badge-orange { @apply bg-orange-50 text-orange-600; }
.badge-red { @apply bg-red-50 text-red-600; }
.badge-green { @apply bg-green-50 text-green-600; }
.badge-gray { @apply bg-gray-100 text-gray-500; }
.badge-green { @apply bg-green-50 text-green-600; }
.badge-red { @apply bg-red-50 text-red-600; }
.text-danger { @apply text-red-500; }
.text-success { @apply text-green-500; }
.text-warning { @apply text-orange-500; }
.text-primary { @apply text-blue-600; }
</style>
