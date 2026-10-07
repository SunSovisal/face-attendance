<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText, unauthorized } from '../api'
import PageHeader from '../components/PageHeader.vue'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()
const currentPassword = ref('')
const nextPassword = ref('')
const confirmPassword = ref('')
const error = ref('')
const notice = ref('')
const saving = ref(false)

async function submit() {
  error.value = ''
  notice.value = ''
  if (nextPassword.value !== confirmPassword.value) {
    error.value = 'The new passwords do not match.'
    return
  }
  saving.value = true
  try {
    await api('/api/auth/password', {
      method: 'POST',
      body: JSON.stringify({
        current_password: currentPassword.value,
        new_password: nextPassword.value,
      }),
    })
    currentPassword.value = ''
    nextPassword.value = ''
    confirmPassword.value = ''
    notice.value = 'Password updated.'
  } catch (err) {
    if (unauthorized(err)) {
      router.push('/login')
      return
    }
    error.value = errorText(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="mx-auto max-w-md space-y-6">
    <PageHeader title="Password" subtitle="Use at least 8 characters." />
    <form class="card card-pad space-y-4" @submit.prevent="submit">
      <label class="block">
        <span class="field-label">Current password</span>
        <input v-model="currentPassword" class="field" type="password" autocomplete="current-password" required />
      </label>
      <label class="block">
        <span class="field-label">New password</span>
        <input v-model="nextPassword" class="field" type="password" autocomplete="new-password" minlength="8" required />
      </label>
      <label class="block">
        <span class="field-label">Confirm new password</span>
        <input v-model="confirmPassword" class="field" type="password" autocomplete="new-password" minlength="8" required />
      </label>
      <p v-if="error" class="notice notice-danger" role="alert">{{ error }}</p>
      <p v-else-if="notice" class="notice notice-good" role="status">{{ notice }}</p>
      <button class="btn btn-block" type="submit" :disabled="saving">{{ saving ? 'Saving…' : 'Update password' }}</button>
    </form>
    <p v-if="auth.me && auth.me.status !== 'active'" class="muted text-center">
      <RouterLink class="font-medium text-ink underline underline-offset-4" to="/waiting">Back</RouterLink>
    </p>
  </section>
</template>
