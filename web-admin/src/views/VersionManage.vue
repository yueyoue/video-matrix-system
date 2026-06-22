<template>
  <div>
    <!-- 发布新版本 -->
    <div class="bg-white rounded-card shadow-card p-6 mb-6">
      <h3 class="text-base font-semibold text-gray-900 mb-5">发布新版本</h3>
      <div class="grid grid-cols-2 gap-x-8 gap-y-4 max-w-3xl">
        <div class="form-group">
          <label class="form-label">版本号</label>
          <input v-model="form.version" class="form-input" placeholder="如 1.0.0" />
        </div>
        <div class="form-group">
          <label class="form-label">安装包</label>
          <div class="flex items-center gap-3">
            <input ref="fileInput" type="file" class="hidden" accept=".zip,.exe,.dmg,.apk" @change="handleFileChange" />
            <button class="btn-default" @click="$refs.fileInput.click()">
              <i class="fas fa-upload"></i> 选择文件
            </button>
            <span v-if="form.file" class="text-sm text-gray-600 truncate max-w-xs">{{ form.file.name }}</span>
            <span v-else class="text-sm text-gray-400">未选择文件</span>
          </div>
        </div>
        <div class="form-group col-span-2">
          <label class="form-label">更新日志</label>
          <textarea v-model="form.changelog" class="form-textarea" rows="3" placeholder="请输入更新日志，每行一条"></textarea>
        </div>
      </div>
      <button class="btn-primary mt-4" @click="handlePublish" :disabled="publishing">
        <i class="fas fa-cloud-upload-alt"></i> {{ publishing ? '发布中...' : '发布版本' }}
      </button>
    </div>

    <!-- 历史版本列表 -->
    <div class="table-container">
      <div class="px-6 py-4 border-b border-border">
        <h3 class="text-base font-semibold text-gray-900">历史版本</h3>
      </div>
      <table>
        <thead>
          <tr>
            <th>版本号</th>
            <th>更新日志</th>
            <th>发布时间</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading" v-for="i in 3" :key="i">
            <td v-for="j in 5" :key="j"><div class="h-4 bg-gray-100 rounded animate-pulse w-20"></div></td>
          </tr>
          <tr v-else-if="versions.length === 0">
            <td colspan="5" class="text-center text-gray-400 py-8">暂无版本</td>
          </tr>
          <tr v-else v-for="v in versions" :key="v.id">
            <td class="font-medium">{{ v.version }}</td>
            <td class="max-w-xs truncate text-gray-500">{{ v.changelog }}</td>
            <td class="text-gray-400 text-xs">{{ v.createdAt }}</td>
            <td>
              <span :class="['badge', statusClass(v.status)]">{{ statusText(v.status) }}</span>
            </td>
            <td>
              <div class="flex items-center gap-2">
                <button
                  v-if="v.status !== 'active'"
                  class="btn-success btn-sm"
                  @click="handleSetActive(v)"
                >
                  <i class="fas fa-check"></i> 设为当前
                </button>
                <button
                  v-if="v.status === 'draft'"
                  class="btn-warning btn-sm"
                  @click="handlePublishVersion(v)"
                >
                  <i class="fas fa-rocket"></i> 发布
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, inject } from 'vue'
import { getVersions, createVersion, updateVersion } from '../api/versions'

const showToast = inject('showToast')
const loading = ref(true)
const publishing = ref(false)
const versions = ref([])
const form = reactive({ version: '', changelog: '', file: null })

function statusClass(status) {
  const map = { active: 'badge-green', draft: 'badge-gray', deprecated: 'badge-red' }
  return map[status] || 'badge-gray'
}

function statusText(status) {
  const map = { active: '当前版本', draft: '草稿', deprecated: '已废弃' }
  return map[status] || status
}

function handleFileChange(e) {
  form.file = e.target.files[0] || null
}

async function fetchVersions() {
  loading.value = true
  try {
    const res = await getVersions()
    versions.value = res.data || []
  } catch (e) {
    showToast(e.message || '获取版本列表失败', 'error')
  } finally {
    loading.value = false
  }
}

async function handlePublish() {
  if (!form.version) {
    showToast('请输入版本号', 'warning')
    return
  }
  publishing.value = true
  try {
    const fd = new FormData()
    fd.append('version', form.version)
    fd.append('changelog', form.changelog)
    if (form.file) fd.append('file', form.file)
    await createVersion(fd)
    showToast('版本发布成功')
    form.version = ''
    form.changelog = ''
    form.file = null
    fetchVersions()
  } catch (e) {
    showToast(e.message || '发布失败', 'error')
  } finally {
    publishing.value = false
  }
}

async function handleSetActive(version) {
  try {
    await updateVersion(version.id, { status: 'active' })
    showToast('已设为当前版本')
    fetchVersions()
  } catch (e) {
    showToast(e.message || '操作失败', 'error')
  }
}

async function handlePublishVersion(version) {
  try {
    await updateVersion(version.id, { status: 'active' })
    showToast('版本已发布')
    fetchVersions()
  } catch (e) {
    showToast(e.message || '操作失败', 'error')
  }
}

onMounted(fetchVersions)
</script>
