import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api'

export type Me = {
  id: number
  username: string
  role: 'super_admin' | 'admin' | 'employee'
  status: 'pending' | 'active' | 'disabled'
  employee_id: number | null
  employee_name: string | null
}

export const useAuthStore = defineStore('auth', () => {
  const me = ref<Me | null>(null)
  const ready = ref(false)

  async function fetchMe() {
    const response = await fetch('/api/auth/me', { credentials: 'include' })
    me.value = response.ok ? ((await response.json()) as Me) : null
    ready.value = true
  }

  async function login(username: string, password: string) {
    me.value = await api<Me>('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
    ready.value = true
  }

  async function register(fullName: string, username: string, password: string) {
    me.value = await api<Me>('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ full_name: fullName, username, password }),
    })
    ready.value = true
  }

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
    me.value = null
  }

  return { me, ready, fetchMe, login, register, logout }
})
