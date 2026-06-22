<template>
  <router-view />
  <div v-if="toast.show" :class="['toast', `toast-${toast.type}`]">
    <i :class="toastIcon" class="mr-2"></i>
    {{ toast.message }}
  </div>
</template>

<script setup>
import { reactive, computed, provide } from 'vue'

const toast = reactive({ show: false, message: '', type: 'success', timer: null })

const toastIcons = {
  success: 'fas fa-check-circle',
  error: 'fas fa-times-circle',
  warning: 'fas fa-exclamation-circle'
}

const toastIcon = computed(() => toastIcons[toast.type] || toastIcons.success)

function showToast(message, type = 'success', duration = 3000) {
  if (toast.timer) clearTimeout(toast.timer)
  toast.show = true
  toast.message = message
  toast.type = type
  toast.timer = setTimeout(() => {
    toast.show = false
  }, duration)
}

provide('showToast', showToast)
</script>
