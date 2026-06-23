import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, getUserInfo } from '../api/auth'

export const useUserStore = defineStore('user', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref((() => {
  try {
    const v = localStorage.getItem('user')
    return v && v !== 'undefined' ? JSON.parse(v) : null
  } catch { return null }
})())

  async function login(username, password) {
    const res = await loginApi({ username, password })
    token.value = res.data.token
    const u = res.data.userInfo || res.data.user || { username }
    user.value = u
    localStorage.setItem('token', res.data.token)
    localStorage.setItem('user', JSON.stringify(u))
    return res
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  async function fetchUserInfo() {
    const res = await getUserInfo()
    user.value = res.data
    localStorage.setItem('user', JSON.stringify(res.data))
    return res
  }

  return { token, user, login, logout, fetchUserInfo }
})
