<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText, unauthorized } from '../api'
import PageHeader from '../components/PageHeader.vue'
import StatusChip from '../components/StatusChip.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { roleLabel } from '../format'

type Account = {
  id: number
  username: string
  role: string
  status: string
  employee_name: string | null
}

const router = useRouter()
const rows = ref<Account[]>([])
const loading = ref(true)
const error = ref('')
const busyId = ref<number | null>(null)
const view = ref('all')
const passwordId = ref<number | null>(null)
const nextPassword = ref('')
const confirmPassword = ref('')
const notice = ref('')

const views = computed(() => [
  { key: 'all', label: 'All', count: rows.value.length },
  { key: 'pending', label: 'Pending', count: rows.value.filter((row) => row.status === 'pending').length },
  { key: 'admins', label: 'Admins', count: rows.value.filter((row) => row.role !== 'employee').length },
  { key: 'disabled', label: 'Disabled', count: rows.value.filter((row) => row.status === 'disabled').length },
])

const shown = computed(() => {
  if (view.value === 'pending') return rows.value.filter((row) => row.status === 'pending')
  if (view.value === 'admins') return rows.value.filter((row) => row.role !== 'employee')
  if (view.value === 'disabled') return rows.value.filter((row) => row.status === 'disabled')
  return rows.value
})

function fail(err: unknown) {
  if (unauthorized(err)) {
    router.push('/login')
    return true
  }
  return false
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    rows.value = await api<Account[]>('/api/accounts')
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    loading.value = false
  }
}

const confirmText: Record<string, (name: string) => string> = {
  disable: (name) => `Disable ${name}? They will be signed out and cannot log in.`,
  promote: (name) => `Make ${name} an admin? They will see everyone's attendance.`,
  demote: (name) => `Make ${name} a regular employee again?`,
}

function startPassword(account: Account) {
  passwordId.value = passwordId.value === account.id ? null : account.id
  nextPassword.value = ''
  confirmPassword.value = ''
  error.value = ''
}

async function savePassword(account: Account) {
  error.value = ''
  notice.value = ''
  if (nextPassword.value !== confirmPassword.value) {
    error.value = 'The passwords do not match.'
    return
  }
  busyId.value = account.id
  try {
    await api(`/api/accounts/${account.id}/password`, {
      method: 'POST',
      body: JSON.stringify({ password: nextPassword.value }),
    })
    const name = account.employee_name || account.username
    notice.value = `Password updated for ${name}. Tell them the new one.`
    passwordId.value = null
    nextPassword.value = ''
    confirmPassword.value = ''
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    busyId.value = null
  }
}

async function act(account: Account, action: 'activate' | 'disable' | 'promote' | 'demote') {
  const name = account.employee_name || account.username
  const ask = action === 'disable' && account.status === 'pending' ? `Reject ${name}'s sign-up?` : confirmText[action]?.(name)
  if (ask && !window.confirm(ask)) return
  busyId.value = account.id
  error.value = ''
  try {
    await api(`/api/accounts/${account.id}/${action}`, { method: 'POST' })
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    busyId.value = null
  }
}

onMounted(async () => {
  await load()
  if (rows.value.some((row) => row.status === 'pending')) view.value = 'pending'
})
</script>

<template>
  <section class="space-y-6">
    <PageHeader title="Accounts" subtitle="Approve sign-ups, promote employees to admin, or turn a login off." />

    <div class="segmented" role="group" aria-label="Show">
      <button v-for="item in views" :key="item.key" type="button" :aria-pressed="view === item.key" @click="view = item.key">
        {{ item.label }} <span class="opacity-60">{{ item.count }}</span>
      </button>
    </div>

    <p v-if="notice" class="notice notice-good" role="status">{{ notice }}</p>
    <p v-if="error" class="notice notice-danger">{{ error }}</p>
    <p v-if="loading && rows.length === 0" class="muted">Loading…</p>
    <div v-else-if="shown.length === 0" class="card empty">
      <p class="section-title">Nothing here</p>
      <p class="muted">No accounts match this view.</p>
    </div>
    <ul v-else class="card list">
      <li v-for="account in shown" :key="account.id" class="space-y-3 px-5 py-4">
        <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
        <div class="flex min-w-0 flex-1 items-center gap-3">
          <UserAvatar :name="account.employee_name || account.username" />
          <div class="min-w-0">
            <p class="truncate font-medium">{{ account.employee_name || account.username }}</p>
            <p class="truncate text-xs text-mute">@{{ account.username }}</p>
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span class="chip" :class="{ 'chip-neutral': account.role !== 'employee' }">{{ roleLabel(account.role) }}</span>
          <StatusChip :status="account.status" />
        </div>
        <div v-if="account.role !== 'super_admin'" class="flex w-full flex-wrap justify-end gap-2 sm:w-auto">
          <button
            v-if="account.status !== 'active'"
            class="btn btn-sm"
            type="button"
            :disabled="busyId === account.id"
            @click="act(account, 'activate')"
          >
            {{ account.status === 'pending' ? 'Approve' : 'Re-enable' }}
          </button>
          <button
            v-if="account.role === 'employee' && account.status === 'active'"
            class="btn-quiet btn-sm"
            type="button"
            :disabled="busyId === account.id"
            @click="act(account, 'promote')"
          >
            Make admin
          </button>
          <button
            v-if="account.role === 'admin'"
            class="btn-quiet btn-sm"
            type="button"
            :disabled="busyId === account.id"
            @click="act(account, 'demote')"
          >
            Make employee
          </button>
          <button
            v-if="account.status !== 'disabled'"
            class="btn-danger btn-sm"
            type="button"
            :disabled="busyId === account.id"
            @click="act(account, 'disable')"
          >
            {{ account.status === 'pending' ? 'Reject' : 'Disable' }}
          </button>
          <button class="btn-quiet btn-sm" type="button" :aria-expanded="passwordId === account.id" @click="startPassword(account)">
            Set password
          </button>
        </div>
        <p v-else class="w-full text-right text-xs text-mute sm:w-auto">That's you</p>
        </div>
        <form
          v-if="passwordId === account.id"
          class="grid gap-3 rounded-xl bg-soft p-4 sm:grid-cols-[1fr_1fr_auto]"
          @submit.prevent="savePassword(account)"
        >
          <label>
            <span class="field-label">New password</span>
            <input v-model="nextPassword" class="field" type="password" autocomplete="new-password" minlength="8" required />
          </label>
          <label>
            <span class="field-label">Confirm</span>
            <input v-model="confirmPassword" class="field" type="password" autocomplete="new-password" minlength="8" required />
          </label>
          <div class="flex items-end gap-2">
            <button class="btn" type="submit" :disabled="busyId === account.id">Save</button>
            <button class="btn-quiet" type="button" @click="passwordId = null">Cancel</button>
          </div>
          <p class="hint sm:col-span-3 !mt-0">At least 8 characters. Tell them the new password. Their old one stops working.</p>
        </form>
      </li>
    </ul>
  </section>
</template>
