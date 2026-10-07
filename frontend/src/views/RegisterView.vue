<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { errorText } from '../api'
import { homeFor } from '../router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const fullName = ref('')
const username = ref('')
const password = ref('')
const error = ref('')
const saving = ref(false)

async function submit() {
  error.value = ''
  saving.value = true
  try {
    await auth.register(fullName.value, username.value, password.value)
    if (auth.me) router.push(homeFor(auth.me))
  } catch (err) {
    error.value = errorText(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="w-full max-w-sm space-y-6">
    <div class="flex items-center gap-2.5">
      <span class="brand-mark" aria-hidden="true">A</span>
      <span class="text-sm font-semibold tracking-tight">Attendance</span>
    </div>
    <form class="card card-pad space-y-5" @submit.prevent="submit">
      <div class="space-y-1">
        <h1 class="page-title">Create an account</h1>
        <p class="muted">An admin approves new accounts before you can sign in fully.</p>
      </div>
      <label class="block">
        <span class="field-label">Full name</span>
        <input v-model="fullName" class="field" autocomplete="name" placeholder="As it should appear on the roster" required />
      </label>
      <label class="block">
        <span class="field-label">Username</span>
        <input v-model="username" class="field" autocomplete="username" required />
      </label>
      <label class="block">
        <span class="field-label">Password</span>
        <input v-model="password" class="field" type="password" autocomplete="new-password" minlength="8" required />
        <p class="hint">At least 8 characters.</p>
      </label>
      <p v-if="error" class="notice notice-danger" role="alert">{{ error }}</p>
      <button class="btn btn-block" type="submit" :disabled="saving">{{ saving ? 'Creating…' : 'Create account' }}</button>
    </form>
    <p class="muted text-center">
      Already registered?
      <RouterLink class="font-medium text-ink underline underline-offset-4" to="/login">Sign in</RouterLink>
    </p>
  </div>
</template>
