<template>
  <div>
    <!-- Tab 切换 -->
    <div class="flex gap-1 mb-6 bg-white rounded-card shadow-card p-1.5 w-fit">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="[
          'px-5 py-2 rounded-btn text-sm font-medium transition-colors',
          activeTab === tab.key
            ? 'bg-primary text-white'
            : 'text-gray-600 hover:bg-gray-50'
        ]"
        @click="switchTab(tab.key)"
      >
        <i :class="tab.icon" class="mr-1.5"></i>{{ tab.label }}
      </button>
    </div>

    <!-- 配置表单 -->
    <div class="bg-white rounded-card shadow-card p-6">
      <div v-if="loading" class="flex items-center justify-center py-12">
        <div class="loading-spinner !border-gray-300 !border-t-primary"></div>
      </div>
      <template v-else>
        <div class="grid grid-cols-2 gap-x-8 gap-y-4 max-w-4xl">
          <div v-for="field in currentFields" :key="field.key" class="form-group">
            <label class="form-label">{{ field.label }}</label>
            <input
              v-if="field.type !== 'textarea'"
              v-model="form[field.key]"
              :type="field.type || 'text'"
              class="form-input"
              :placeholder="field.placeholder || ''"
            />
            <textarea
              v-else
              v-model="form[field.key]"
              class="form-textarea"
              rows="3"
              :placeholder="field.placeholder || ''"
            ></textarea>
          </div>
        </div>
        <div class="flex gap-3 mt-6 pt-5 border-t border-border">
          <button class="btn-primary" @click="handleSave" :disabled="saving">
            <i class="fas fa-save"></i> {{ saving ? '保存中...' : '保存配置' }}
          </button>
          <button class="btn-default" @click="handleReset">
            <i class="fas fa-undo"></i> 恢复默认
          </button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, inject } from 'vue'
import { getPlatformConfig, updatePlatformConfig, resetPlatformConfig } from '../api/platform'

const showToast = inject('showToast')
const loading = ref(false)
const saving = ref(false)
const activeTab = ref('douyin')

const tabs = [
  { key: 'douyin', label: '抖音', icon: 'fab fa-tiktok' },
  { key: 'kuaishou', label: '快手', icon: 'fas fa-bolt' },
  { key: 'xiaohongshu', label: '小红书', icon: 'fas fa-book' },
  { key: 'shipinhao', label: '视频号', icon: 'fas fa-play-circle' },
]

const platformFields = {
  douyin: [
    { key: 'appId', label: 'App ID', placeholder: '请输入抖音App ID' },
    { key: 'appSecret', label: 'App Secret', type: 'password', placeholder: '请输入App Secret' },
    { key: 'callbackUrl', label: '回调地址', placeholder: 'https://your-domain.com/callback' },
    { key: 'maxPublish', label: '每日发布上限', type: 'number', placeholder: '50' },
    { key: 'description', label: '备注', type: 'textarea', placeholder: '配置备注信息' },
  ],
  kuaishou: [
    { key: 'appId', label: 'App ID', placeholder: '请输入快手App ID' },
    { key: 'appSecret', label: 'App Secret', type: 'password', placeholder: '请输入App Secret' },
    { key: 'callbackUrl', label: '回调地址', placeholder: 'https://your-domain.com/callback' },
    { key: 'maxPublish', label: '每日发布上限', type: 'number', placeholder: '50' },
    { key: 'description', label: '备注', type: 'textarea', placeholder: '配置备注信息' },
  ],
  xiaohongshu: [
    { key: 'appId', label: 'App ID', placeholder: '请输入小红书App ID' },
    { key: 'appSecret', label: 'App Secret', type: 'password', placeholder: '请输入App Secret' },
    { key: 'callbackUrl', label: '回调地址', placeholder: 'https://your-domain.com/callback' },
    { key: 'maxPublish', label: '每日发布上限', type: 'number', placeholder: '30' },
    { key: 'description', label: '备注', type: 'textarea', placeholder: '配置备注信息' },
  ],
  shipinhao: [
    { key: 'appId', label: 'App ID', placeholder: '请输入视频号App ID' },
    { key: 'appSecret', label: 'App Secret', type: 'password', placeholder: '请输入App Secret' },
    { key: 'callbackUrl', label: '回调地址', placeholder: 'https://your-domain.com/callback' },
    { key: 'maxPublish', label: '每日发布上限', type: 'number', placeholder: '50' },
    { key: 'description', label: '备注', type: 'textarea', placeholder: '配置备注信息' },
  ],
}

const currentFields = computed(() => platformFields[activeTab.value] || [])
const form = reactive({})

function resetForm(data = {}) {
  const fields = platformFields[activeTab.value] || []
  fields.forEach(f => {
    form[f.key] = data[f.key] ?? ''
  })
}

async function fetchConfig(platform) {
  loading.value = true
  try {
    const res = await getPlatformConfig(platform)
    resetForm(res.data || {})
  } catch (e) {
    resetForm()
    console.error('获取配置失败:', e)
  } finally {
    loading.value = false
  }
}

function switchTab(key) {
  activeTab.value = key
  fetchConfig(key)
}

async function handleSave() {
  saving.value = true
  try {
    await updatePlatformConfig(activeTab.value, { ...form })
    showToast('配置保存成功')
  } catch (e) {
    showToast(e.message || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function handleReset() {
  if (!confirm('确定要恢复默认配置吗？当前修改将丢失。')) return
  try {
    const res = await resetPlatformConfig(activeTab.value)
    resetForm(res.data || {})
    showToast('已恢复默认配置')
  } catch (e) {
    showToast(e.message || '恢复失败', 'error')
  }
}

onMounted(() => fetchConfig(activeTab.value))
</script>
