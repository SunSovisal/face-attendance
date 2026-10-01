<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

type Person = { id: number; name: string }
type Row = {
  id: number
  person_id: number | null
  person_name: string
  timestamp: string
  local_date: string
  distance: number
}

const router = useRouter()
const people = ref<Person[]>([])
const rows = ref<Row[]>([])
const loading = ref(true)
const error = ref('')
const personId = ref('')
const fromDate = ref(today())
const toDate = ref(today())

function today() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Phnom_Penh' }).format(new Date())
}

function formatWhen(timestamp: string) {
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return timestamp
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'Asia/Phnom_Penh',
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date)
}

async function loadPeople() {
  const response = await fetch('/api/people', { credentials: 'include' })
  if (response.status === 401) {
    router.push('/login')
    return
  }
  if (!response.ok) return
  people.value = await response.json()
}

async function loadAttendance() {
  loading.value = true
  error.value = ''
  const params = new URLSearchParams()
  if (personId.value) params.set('person_id', personId.value)
  if (fromDate.value) params.set('from', fromDate.value)
  if (toDate.value) params.set('to', toDate.value)
  const response = await fetch(`/api/attendance?${params}`, { credentials: 'include' })
  if (response.status === 401) {
    router.push('/login')
    return
  }
  if (!response.ok) {
    error.value = 'Could not load attendance.'
    loading.value = false
    return
  }
  rows.value = await response.json()
  loading.value = false
}

watch([personId, fromDate, toDate], () => {
  void loadAttendance()
})

onMounted(async () => {
  await Promise.all([loadPeople(), loadAttendance()])
})
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div class="space-y-1">
        <h1 class="page-title">Attendance</h1>
        <p class="muted">Confirmed check-ins, newest first.</p>
      </div>
      <span v-if="!loading" class="chip">{{ rows.length }} check-in{{ rows.length === 1 ? '' : 's' }}</span>
    </div>

    <form class="card card-pad grid gap-4 sm:grid-cols-3">
      <label>
        <span class="field-label">Person</span>
        <select v-model="personId" class="field">
          <option value="">Everyone</option>
          <option v-for="person in people" :key="person.id" :value="String(person.id)">{{ person.name }}</option>
        </select>
      </label>
      <label>
        <span class="field-label">From</span>
        <input v-model="fromDate" class="field" type="date" />
      </label>
      <label>
        <span class="field-label">To</span>
        <input v-model="toDate" class="field" type="date" />
      </label>
    </form>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <div v-else-if="rows.length === 0" class="card card-pad">
      <p class="muted">No check-ins in this range. Confirmed matches from the Live page show up here.</p>
    </div>
    <div v-else class="card overflow-hidden">
      <table class="w-full text-left text-sm">
        <thead class="border-b border-line">
          <tr>
            <th class="px-6 py-3 font-medium">Name</th>
            <th class="px-6 py-3 font-medium">Time</th>
            <th class="px-6 py-3 font-medium">Distance</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" class="border-b border-line last:border-b-0">
            <td class="px-6 py-4">{{ row.person_name }}</td>
            <td class="px-6 py-4 text-mute">{{ formatWhen(row.timestamp) }}</td>
            <td class="px-6 py-4 text-mute">{{ row.distance.toFixed(2) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
