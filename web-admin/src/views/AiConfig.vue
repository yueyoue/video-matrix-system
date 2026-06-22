<template>
  <div>
    <!-- AI接口基础配置 -->
    <div class="bg-white rounded-card shadow-card p-6 mb-6">
      <h3 class="text-base font-semibold text-gray-900 mb-5">AI接口配置</h3>
      <div class="grid grid-cols-2 gap-x-8 gap-y-4 max-w-3xl">
        <div class="form-group">
          <label class="form-label">服务商</label>
          <select v-model="config.provider" class="form-select">
            <option value="azure">Azure TTS</option>
            <option value="aliyun">阿里云</option>
            <option value="baidu">百度</option>
            <option value="custom">自定义</option>
          </select>
        </div>
        <div class="form-group">
          <label class="form-label">API地址</label>
          <input v-model="config.apiUrl" class="form-input" placeholder="https://api.example.com" />
        </div>
        <div class="form-group">
          <label class="form-label">AppID</label>
          <input v-model="config.appId" class="form-input" placeholder="请输入AppID" />
        </div>
        <div class="form-group">
          <label class="form-label">密钥</label>
          <input v-model="config.apiKey" type="password" class="form-input" placeholder="请输入密钥" />
        </div>
        <div class="form-group">
          <label class="form-label">每日调用上限</label>
          <input v-model.number="config.dailyLimit" type="number" class="form-input" placeholder="1000" />
        </div>
      </div>
      <div class="flex gap-3 mt-5">
        <button class="btn-primary" @click="handleSaveConfig" :disabled="saving">
          <i class="fas fa-save"></i> {{ saving ? '保存中...' : '保存配置' }}
        </button>
        <button class="btn-default" @click="handleTestConnection" :disabled="testing">
          <i class="fas fa-plug"></i> {{ testing ? '测试中...' : '测试连接' }}
        </button>
      </div>
    </div>

    <!-- 音色列表 -->
    <div class="bg-white rounded-card shadow-card overflow-hidden">
      <div class="px-6 py-4 border-b border-border flex items-center justify-between">
        <h3 class="text-base font-semibold text-gray-900">音色列表</h3>
        <button class="btn-primary btn-sm" @click="openVoiceModal()">
          <i class="fas fa-plus"></i> 添加音色
        </button>
      </div>
      <table class="w-full">
        <thead>
          <tr>
            <th class="bg-gray-50 text-gray-500 text-xs font-medium px-6 py-3 text-left border-b border-border">音色ID</th>
            <th class="bg-gray-50 text-gray-500 text-xs font-medium px-6 py-3 text-left border-b border-border">名称</th>
            <th class="bg-gray-50 text-gray-500 text-xs font-medium px-6 py-3 text-left border-b border-border">语言</th>
            <th class="bg-gray-50 text-gray-500 text-xs font-medium px-6 py-3 text-left border-b border-border">状态</th>
            <th class="bg-gray-50 text-gray-500 text-xs font-medium px-6 py-3 text-left border-b border-border">操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loadingVoices" v-for="i in 3" :key="i">
            <td colspan="5" class="px-6 py-3"><div class="h-4 bg-gray-100 rounded animate-pulse w-32"></div></td>
          </tr>
          <tr v-else-if="voices.length === 0">
            <td colspan="5" class="text-center text-gray-400 py-8">暂无音色</td>
          </tr>
          <tr v-else v-for="voice in voices" :key="voice.id" class="border-b border-gray-100 hover:bg-blue-50/50">
            <td class="px-6 py-3 text-sm">{{ voice.voiceId }}</td>
            <td class="px-6 py-3 text-sm font-medium">{{ voice.name }}</td>
            <td class="px-6 py-3 text-sm">{{ voice.language }}</td>
            <td class="px-6 py-3">
              <span :class="['badge', voice.enabled ? 'badge-green' : 'badge-gray']">
                {{ voice.enabled ? '启用' : '禁用' }}
              </span>
            </td>
            <td class="px-6 py-3">
              <div class="flex items-center gap-2">
                <button class="btn-default btn-sm" @click="openVoiceModal(voice)">
                  <i class="fas fa-edit"></i>
                </button>
                <button class="btn-danger btn-sm" @click="handleDeleteVoice(voice)">
                  <i class="fas fa-trash"></i>
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 音色弹窗 -->
    <div v-if="voiceModalVisible" class="modal-overlay" @click.self="voiceModalVisible = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ editingVoice ? '编辑音色' : '添加音色' }}</h3>
          <button @click="voiceModalVisible = false" class="text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">音色ID</label>
            <input v-model="voiceForm.voiceId" class="form-input" placeholder="如 zh-CN-XiaoxiaoNeural" />
          </div>
          <div class="form-group">
            <label class="form-label">名称</label>
            <input v-model="voiceForm.name" class="form-input" placeholder="请输入音色名称" />
          </div>
          <div class="form-group">
            <label class="form-label">语言</label>
            <input v-model="voiceForm.language" class="form-input" placeholder="如 zh-CN" />
          </div>
          <div class="form-group">
            <label class="form-label">状态</label>
            <select v-model="voiceForm.enabled" class="form-select">
              <option :value="true">启用</option>
              <option :value="false">禁用</option>
            </select>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-default" @click="voiceModalVisible = false">取消</button>
          <button class="btn-primary" @click="handleSaveVoice" :disabled="savingVoice">
            {{ savingVoice ? '保存中...' : '确定' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, inject } from 'vue'
import { getAiConfig, updateAiConfig, testAiConnection, getVoices, createVoice, updateVoice, deleteVoice } from '../api/ai'

const showToast = inject('showToast')
const saving = ref(false)
const testing = ref(false)
const loadingVoices = ref(true)
const savingVoice = ref(false)

const config = reactive({
  provider: 'azure',
  apiUrl: '',
  appId: '',
  apiKey: '',
  dailyLimit: 1000
})

const voices = ref([])
const voiceModalVisible = ref(false)
const editingVoice = ref(null)
const voiceForm = reactive({ voiceId: '', name: '', language: '', enabled: true })

async function fetchConfig() {
  try {
    const res = await getAiConfig()
    Object.assign(config, res.data)
  } catch (e) {
    console.error('获取AI配置失败:', e)
  }
}

async function fetchVoices() {
  loadingVoices.value = true
  try {
    const res = await getVoices()
    voices.value = res.data || []
  } catch (e) {
    showToast(e.message || '获取音色列表失败', 'error')
  } finally {
    loadingVoices.value = false
  }
}

async function handleSaveConfig() {
  saving.value = true
  try {
    await updateAiConfig({ ...config })
    showToast('配置保存成功')
  } catch (e) {
    showToast(e.message || '保存失败', 'error')
  } finally {
    saving.value = false
  }
}

async function handleTestConnection() {
  testing.value = true
  try {
    await testAiConnection()
    showToast('连接测试成功')
  } catch (e) {
    showToast(e.message || '连接测试失败', 'error')
  } finally {
    testing.value = false
  }
}

function openVoiceModal(voice = null) {
  editingVoice.value = voice
  if (voice) {
    Object.assign(voiceForm, { voiceId: voice.voiceId, name: voice.name, language: voice.language, enabled: voice.enabled })
  } else {
    Object.assign(voiceForm, { voiceId: '', name: '', language: '', enabled: true })
  }
  voiceModalVisible.value = true
}

async function handleSaveVoice() {
  if (!voiceForm.voiceId || !voiceForm.name) {
    showToast('请填写完整信息', 'warning')
    return
  }
  savingVoice.value = true
  try {
    if (editingVoice.value) {
      await updateVoice(editingVoice.value.id, { ...voiceForm })
      showToast('音色更新成功')
    } else {
      await createVoice({ ...voiceForm })
      showToast('音色添加成功')
    }
    voiceModalVisible.value = false
    fetchVoices()
  } catch (e) {
    showToast(e.message || '操作失败', 'error')
  } finally {
    savingVoice.value = false
  }
}

async function handleDeleteVoice(voice) {
  if (!confirm(`确定删除音色 "${voice.name}" 吗？`)) return
  try {
    await deleteVoice(voice.id)
    showToast('音色已删除')
    fetchVoices()
  } catch (e) {
    showToast(e.message || '删除失败', 'error')
  }
}

onMounted(() => {
  fetchConfig()
  fetchVoices()
})
</script>
