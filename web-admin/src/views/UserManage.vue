<template>
  <div>
    <!-- 顶部操作栏 -->
    <div class="flex items-center justify-between mb-5">
      <div class="flex items-center gap-3">
        <button class="btn-primary" @click="openAddModal">
          <i class="fas fa-plus"></i> 添加用户
        </button>
      </div>
    </div>

    <!-- 用户表格 -->
    <div class="table-container">
      <table>
        <thead>
          <tr>
            <th>用户名</th>
            <th>角色</th>
            <th>状态</th>
            <th>配额</th>
            <th>已用</th>
            <th>最后登录</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading" v-for="i in 5" :key="i">
            <td v-for="j in 7" :key="j"><div class="h-4 bg-gray-100 rounded animate-pulse" :style="{ width: j === 7 ? '120px' : '60px' }"></div></td>
          </tr>
          <tr v-else-if="users.length === 0">
            <td colspan="7" class="text-center text-gray-400 py-8">暂无用户</td>
          </tr>
          <tr v-else v-for="user in users" :key="user.id">
            <td class="font-medium">{{ user.username }}</td>
            <td>
              <span :class="['badge', user.role === 'admin' ? 'badge-blue' : 'badge-gray']">
                {{ user.role === 'admin' ? '管理员' : '普通用户' }}
              </span>
            </td>
            <td>
              <span :class="['badge', user.status === 'active' ? 'badge-green' : 'badge-red']">
                {{ user.status === 'active' ? '正常' : '已停用' }}
              </span>
            </td>
            <td>{{ user.quota }}</td>
            <td>{{ user.used }}</td>
            <td class="text-gray-400 text-xs">{{ user.lastLogin || '-' }}</td>
            <td>
              <div class="flex items-center gap-2">
                <button class="btn-default btn-sm" @click="openEditModal(user)">
                  <i class="fas fa-edit"></i> 编辑
                </button>
                <button
                  :class="[user.status === 'active' ? 'btn-warning' : 'btn-success', 'btn-sm']"
                  @click="handleToggleStatus(user)"
                >
                  <i :class="user.status === 'active' ? 'fas fa-ban' : 'fas fa-check'"></i>
                  {{ user.status === 'active' ? '停用' : '启用' }}
                </button>
                <button class="btn-danger btn-sm" @click="handleDelete(user)">
                  <i class="fas fa-trash"></i> 删除
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 添加/编辑弹窗 -->
    <div v-if="modalVisible" class="modal-overlay" @click.self="modalVisible = false">
      <div class="modal">
        <div class="modal-header">
          <h3>{{ isEdit ? '编辑用户' : '添加用户' }}</h3>
          <button @click="modalVisible = false" class="text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label class="form-label">用户名</label>
            <input v-model="form.username" class="form-input" placeholder="请输入用户名" :disabled="isEdit" />
          </div>
          <div class="form-group">
            <label class="form-label">{{ isEdit ? '新密码（留空不修改）' : '密码' }}</label>
            <input v-model="form.password" type="password" class="form-input" :placeholder="isEdit ? '留空则不修改密码' : '请输入密码'" />
          </div>
          <div class="form-group">
            <label class="form-label">角色</label>
            <select v-model="form.role" class="form-select">
              <option value="user">普通用户</option>
              <option value="admin">管理员</option>
            </select>
          </div>
          <div class="form-group">
            <label class="form-label">每日配额</label>
            <input v-model.number="form.quota" type="number" class="form-input" placeholder="请输入每日视频配额" />
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn-default" @click="modalVisible = false">取消</button>
          <button class="btn-primary" @click="handleSubmit" :disabled="submitting">
            <span v-if="submitting" class="loading-spinner"></span>
            {{ submitting ? '提交中...' : '确定' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div v-if="deleteModalVisible" class="modal-overlay" @click.self="deleteModalVisible = false">
      <div class="modal">
        <div class="modal-header">
          <h3>确认删除</h3>
          <button @click="deleteModalVisible = false" class="text-gray-400 hover:text-gray-600">
            <i class="fas fa-times"></i>
          </button>
        </div>
        <div class="modal-body">
          <p class="text-sm text-gray-600">确定要删除用户 <strong>{{ deleteTarget?.username }}</strong> 吗？此操作不可恢复。</p>
        </div>
        <div class="modal-footer">
          <button class="btn-default" @click="deleteModalVisible = false">取消</button>
          <button class="btn-danger" @click="confirmDelete" :disabled="submitting">
            <span v-if="submitting" class="loading-spinner"></span>
            确认删除
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, inject } from 'vue'
import { getUsers, createUser, updateUser, deleteUser, toggleUserStatus } from '../api/users'

const showToast = inject('showToast')
const loading = ref(true)
const submitting = ref(false)
const users = ref([])

// 弹窗状态
const modalVisible = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const form = reactive({ username: '', password: '', role: 'user', quota: 10 })

// 删除弹窗
const deleteModalVisible = ref(false)
const deleteTarget = ref(null)

async function fetchUsers() {
  loading.value = true
  try {
    const res = await getUsers()
    users.value = res.data || []
  } catch (e) {
    showToast(e.message || '获取用户列表失败', 'error')
  } finally {
    loading.value = false
  }
}

function openAddModal() {
  isEdit.value = false
  editId.value = null
  Object.assign(form, { username: '', password: '', role: 'user', quota: 10 })
  modalVisible.value = true
}

function openEditModal(user) {
  isEdit.value = true
  editId.value = user.id
  Object.assign(form, { username: user.username, password: '', role: user.role, quota: user.quota })
  modalVisible.value = true
}

async function handleSubmit() {
  if (!form.username) {
    showToast('请输入用户名', 'warning')
    return
  }
  if (!isEdit.value && !form.password) {
    showToast('请输入密码', 'warning')
    return
  }
  submitting.value = true
  try {
    const data = { ...form }
    if (isEdit.value && !data.password) delete data.password
    if (isEdit.value) {
      await updateUser(editId.value, data)
      showToast('用户更新成功')
    } else {
      await createUser(data)
      showToast('用户创建成功')
    }
    modalVisible.value = false
    fetchUsers()
  } catch (e) {
    showToast(e.message || '操作失败', 'error')
  } finally {
    submitting.value = false
  }
}

async function handleToggleStatus(user) {
  const newStatus = user.status === 'active' ? 'disabled' : 'active'
  try {
    await toggleUserStatus(user.id, newStatus)
    showToast(`用户已${newStatus === 'active' ? '启用' : '停用'}`)
    fetchUsers()
  } catch (e) {
    showToast(e.message || '操作失败', 'error')
  }
}

function handleDelete(user) {
  deleteTarget.value = user
  deleteModalVisible.value = true
}

async function confirmDelete() {
  submitting.value = true
  try {
    await deleteUser(deleteTarget.value.id)
    showToast('用户已删除')
    deleteModalVisible.value = false
    fetchUsers()
  } catch (e) {
    showToast(e.message || '删除失败', 'error')
  } finally {
    submitting.value = false
  }
}

onMounted(fetchUsers)
</script>
