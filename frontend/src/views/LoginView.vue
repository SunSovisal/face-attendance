<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const username = ref('admin')
const password = ref('')
const error = ref('')

async function submit() {
  error.value = ''
  try {
    await auth.login(username.value, password.value)
    router.push('/live')
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Login failed'
  }
}
</script>

<template>
  <form class="card card-pad w-full max-w-sm space-y-5" @submit.prevent="submit">
      <div class="space-y-1">
        <p class="muted">Attendance</p>
        <h1 class="page-title">Sign in</h1>
      </div>
      <label>
        <span class="field-label">Username</span>
        <input v-model="username" class="field" autocomplete="username" />
      </label>
      <label>
        <span class="field-label">Password</span>
        <input v-model="password" class="field" type="password" autocomplete="current-password" />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button class="btn w-full" type="submit">Sign in</button>
  </form>
</template>
