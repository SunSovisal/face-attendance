<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText, unauthorized } from '../api'
import FieldSelect from '../components/FieldSelect.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusChip from '../components/StatusChip.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { capitalize, dayCount, formatDay, today } from '../format'
import { useAuthStore } from '../stores/auth'

type Leave = {
  id: number
  employee_name: string
  type: string
  start_date: string
  end_date: string
  note: string
  status: string
}

const router = useRouter()
const auth = useAuthStore()
const rows = ref<Leave[]>([])
const loading = ref(true)
const error = ref('')
const formError = ref('')
const notice = ref('')
const saving = ref(false)
const busyId = ref<number | null>(null)
const type = ref('annual')
const startDate = ref(today())
const endDate = ref(today())
const note = ref('')
const view = ref('pending')
const staff = computed(() => auth.me?.role === 'admin' || auth.me?.role === 'super_admin')
const canRequest = computed(() => Boolean(auth.me?.employee_id))
const requestDays = computed(() => dayCount(startDate.value, endDate.value))

const pendingCount = computed(() => rows.value.filter((row) => row.status === 'pending').length)
const shown = computed(() => {
  if (!staff.value) return rows.value
  if (view.value === 'pending') return rows.value.filter((row) => row.status === 'pending')
  if (view.value === 'decided') return rows.value.filter((row) => row.status !== 'pending')
  return rows.value
})

function span(row: Leave) {
  const days = dayCount(row.start_date, row.end_date)
  const range = row.start_date === row.end_date ? formatDay(row.start_date) : `${formatDay(row.start_date)} – ${formatDay(row.end_date)}`
  return `${range} · ${days} ${days === 1 ? 'day' : 'days'}`
}

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
    rows.value = await api<Leave[]>('/api/leave')
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    loading.value = false
  }
}

async function submit() {
  formError.value = ''
  notice.value = ''
  if (requestDays.value < 1) {
    formError.value = 'The end date must be on or after the start date.'
    return
  }
  saving.value = true
  try {
    await api('/api/leave', {
      method: 'POST',
      body: JSON.stringify({
        type: type.value,
        start_date: startDate.value,
        end_date: endDate.value,
        note: note.value,
      }),
    })
    note.value = ''
    notice.value = 'Request sent. An admin will review it.'
    await load()
  } catch (err) {
    if (!fail(err)) formError.value = errorText(err)
  } finally {
    saving.value = false
  }
}

async function review(row: Leave, decision: 'approve' | 'reject') {
  busyId.value = row.id
  error.value = ''
  try {
    await api(`/api/leave/${row.id}/${decision}`, { method: 'POST' })
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    busyId.value = null
  }
}

onMounted(async () => {
  await load()
  if (staff.value && pendingCount.value === 0) view.value = 'all'
})
</script>

<template>
  <section class="space-y-6">
    <PageHeader
      title="Leave"
      :subtitle="staff ? 'Approved days are not counted as absences.' : 'Ask for time away. An admin approves it.'"
    />

    <div class="grid items-start gap-6" :class="{ 'lg:grid-cols-[22rem_minmax(0,1fr)]': canRequest }">
      <form v-if="canRequest" class="card card-pad space-y-4" @submit.prevent="submit">
        <p class="section-title">Request leave</p>
        <label class="block">
          <span class="field-label">Type</span>
          <FieldSelect
            v-model="type"
            :options="[
              { value: 'annual', label: 'Annual' },
              { value: 'sick', label: 'Sick' },
              { value: 'unpaid', label: 'Unpaid' },
            ]"
          />
        </label>
        <div class="grid grid-cols-2 gap-3">
          <label>
            <span class="field-label">From</span>
            <input v-model="startDate" class="field" type="date" required />
          </label>
          <label>
            <span class="field-label">To</span>
            <input v-model="endDate" class="field" type="date" :min="startDate" required />
          </label>
        </div>
        <label class="block">
          <span class="field-label">Note <span class="normal-case tracking-normal">(optional)</span></span>
          <textarea v-model="note" class="field" rows="2" placeholder="Anything the approver should know"></textarea>
        </label>
        <p v-if="formError" class="error">{{ formError }}</p>
        <p v-else-if="notice" class="notice notice-good" role="status">{{ notice }}</p>
        <button class="btn btn-block" type="submit" :disabled="saving || requestDays < 1">
          {{ saving ? 'Sending…' : `Request ${requestDays > 0 ? requestDays : ''} ${requestDays === 1 ? 'day' : 'days'}` }}
        </button>
      </form>

      <div class="min-w-0 space-y-4">
        <div v-if="staff" class="segmented" role="group" aria-label="Show">
          <button type="button" :aria-pressed="view === 'pending'" @click="view = 'pending'">
            Pending <span class="opacity-60">{{ pendingCount }}</span>
          </button>
          <button type="button" :aria-pressed="view === 'decided'" @click="view = 'decided'">Decided</button>
          <button type="button" :aria-pressed="view === 'all'" @click="view = 'all'">All</button>
        </div>
        <p v-else class="section-title">My requests</p>

        <p v-if="error" class="notice notice-danger">{{ error }}</p>
        <p v-if="loading && rows.length === 0" class="muted">Loading…</p>
        <div v-else-if="shown.length === 0" class="card empty">
          <p class="section-title">{{ staff && view === 'pending' ? 'All caught up' : 'No requests' }}</p>
          <p class="muted">{{ staff && view === 'pending' ? 'No leave is waiting for review.' : 'Leave requests will show up here.' }}</p>
        </div>
        <ul v-else class="card list">
          <li v-for="row in shown" :key="row.id" class="flex flex-wrap items-center gap-x-4 gap-y-3 px-5 py-4">
            <div class="flex min-w-0 flex-1 items-center gap-3">
              <UserAvatar v-if="staff" :name="row.employee_name" />
              <div class="min-w-0">
                <p class="truncate font-medium">
                  {{ staff ? row.employee_name : `${capitalize(row.type)} leave` }}
                  <span v-if="staff" class="font-normal text-mute"> · {{ capitalize(row.type) }}</span>
                </p>
                <p class="num text-xs text-mute">{{ span(row) }}</p>
                <p v-if="row.note" class="mt-1 text-sm text-mute">“{{ row.note }}”</p>
              </div>
            </div>
            <div v-if="staff && row.status === 'pending'" class="flex gap-2">
              <button class="btn btn-sm" type="button" :disabled="busyId === row.id" @click="review(row, 'approve')">Approve</button>
              <button class="btn-quiet btn-sm" type="button" :disabled="busyId === row.id" @click="review(row, 'reject')">Reject</button>
            </div>
            <StatusChip v-else :status="row.status" />
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>
