import { defineStore } from 'pinia'
import { ref } from 'vue'

export type Admin = { id: number; username: string }

export const useAuthStore = defineStore('auth', () => {
  const me = ref<Admin | null>(null)
  const ready = ref(false)

  async function fetchMe() {
    const response = await fetch('/api/auth/me', { credentials: 'include' })
    me.value = response.ok ? await response.json() : null
    ready.value = true
  }

  async function login(username: string, password: string) {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    })
    if (!response.ok) {
      throw new Error('Invalid username or password')
    }
    me.value = await response.json()
    ready.value = true
  }

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' })
    me.value = null
  }

  return { me, ready, fetchMe, login, logout }
})
