<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText, unauthorized } from '../api'
import FieldSelect from '../components/FieldSelect.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusChip from '../components/StatusChip.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { formatDay, formatTime, minutes, weekday } from '../format'

type Department = { id: number; name: string }
type Row = {
  employee_name: string
  department: string
  check_in_at: string | null
  check_out_at: string | null
  status: string
  late_minutes: number
  detail: string
}
type Sheet = {
  local_date: string
  work_start: string
  work_end: string
  grace_minutes: number
  office_closed: boolean
  holiday: string | null
  counts: Record<string, number>
  rows: Row[]
}

const router = useRouter()
const departments = ref<Department[]>([])
const departmentId = ref('')
const sheet = ref<Sheet | null>(null)
const loading = ref(true)
const error = ref('')
const focus = ref('')

const tiles = [
  ['in', 'Checked in'],
  ['due', 'Not in yet'],
  ['late', 'Late'],
  ['incomplete', 'Not checked out'],
  ['left_early', 'Left early'],
  ['absent', 'Absent'],
  ['on_leave', 'On leave'],
] as const

const subtitle = computed(() => {
  if (!sheet.value) return ''
  const day = `${weekday(sheet.value.local_date)} ${formatDay(sheet.value.local_date)}`
  return `${day} · ${sheet.value.work_start}–${sheet.value.work_end}, ${sheet.value.grace_minutes} min grace`
})

const rows = computed(() => {
  const all = sheet.value?.rows ?? []
  if (!focus.value) return all
  if (focus.value === 'in') return all.filter((row) => row.check_in_at)
  return all.filter((row) => row.status === focus.value)
})

function toggleFocus(key: string) {
  focus.value = focus.value === key ? '' : key
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
  const params = new URLSearchParams()
  if (departmentId.value) params.set('department_id', departmentId.value)
  try {
    sheet.value = await api<Sheet>(`/api/attendance/today?${params}`)
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    departments.value = await api<Department[]>('/api/departments')
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  }
  await load()
})
</script>

<template>
  <section class="space-y-6">
    <PageHeader title="Today" :subtitle="subtitle">
      <FieldSelect
        v-if="departments.length"
        v-model="departmentId"
        class="w-44"
        aria-label="Department"
        :options="[{ value: '', label: 'All departments' }, ...departments.map((department) => ({ value: String(department.id), label: department.name }))]"
        @change="load"
      />
      <button class="btn-quiet" type="button" :disabled="loading" @click="load">Refresh</button>
    </PageHeader>

    <p v-if="sheet?.holiday" class="notice notice-warn">Holiday today: {{ sheet.holiday }}. Nobody is expected in.</p>
    <p v-else-if="sheet?.office_closed" class="notice notice-warn">The office is closed today.</p>

    <div v-if="sheet" class="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
      <button
        v-for="[key, label] in tiles"
        :key="key"
        class="stat"
        type="button"
        :aria-pressed="focus === key"
        @click="toggleFocus(key)"
      >
        <span
          class="stat-value"
          :class="{
            'text-danger': key === 'absent' && (sheet.counts[key] ?? 0) > 0,
            'text-warn': (key === 'late' || key === 'left_early') && (sheet.counts[key] ?? 0) > 0,
          }"
        >
          {{ sheet.counts[key] ?? 0 }}
        </span>
        <span class="stat-label">{{ label }}</span>
      </button>
    </div>

    <p v-if="loading && !sheet" class="muted">Loading…</p>
    <p v-else-if="error" class="notice notice-danger">{{ error }}</p>
    <div v-else-if="rows.length === 0" class="card empty">
      <p class="section-title">Nobody here</p>
      <p class="muted">{{ focus ? 'No one matches this tile.' : 'Nothing to show for today.' }}</p>
      <button v-if="focus" class="btn-link mt-1" type="button" @click="focus = ''">Show everyone</button>
    </div>
    <template v-else>
      <div class="card hidden overflow-hidden md:block">
        <table class="data-table">
          <thead>
            <tr>
              <th>Employee</th>
              <th>In</th>
              <th>Out</th>
              <th>Status</th>
              <th>Late</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in rows" :key="`${row.employee_name}-${index}`">
              <td>
                <div class="flex items-center gap-3">
                  <UserAvatar :name="row.employee_name" />
                  <div class="min-w-0">
                    <p class="truncate font-medium">{{ row.employee_name }}</p>
                    <p v-if="row.department" class="truncate text-xs text-mute">{{ row.department }}</p>
                  </div>
                </div>
              </td>
              <td class="num">{{ formatTime(row.check_in_at) }}</td>
              <td class="num">{{ formatTime(row.check_out_at) }}</td>
              <td><StatusChip :status="row.status" /></td>
              <td class="num text-mute">{{ minutes(row.late_minutes) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <ul class="card list md:hidden">
        <li v-for="(row, index) in rows" :key="`${row.employee_name}-${index}`" class="flex items-center gap-3 px-4 py-3">
          <UserAvatar :name="row.employee_name" />
          <div class="min-w-0 flex-1">
            <p class="truncate font-medium">{{ row.employee_name }}</p>
            <p class="num text-xs text-mute">
              In {{ formatTime(row.check_in_at) }} · Out {{ formatTime(row.check_out_at) }}
              <span v-if="row.late_minutes"> · {{ minutes(row.late_minutes) }} late</span>
            </p>
          </div>
          <StatusChip :status="row.status" />
        </li>
      </ul>
    </template>
  </section>
</template>
