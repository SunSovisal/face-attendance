<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorText, unauthorized } from '../api'
import FieldSelect from '../components/FieldSelect.vue'
import PageHeader from '../components/PageHeader.vue'
import StatusChip from '../components/StatusChip.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { formatDay, formatTime, minutes, monthStart, today, weekStart, weekday } from '../format'
import { useAuthStore } from '../stores/auth'

type Person = { id: number; name: string }
type Department = { id: number; name: string }
type Row = {
  id: number | null
  employee_id: number | null
  employee_name: string
  department: string
  local_date: string
  check_in_at: string | null
  check_out_at: string | null
  check_in_manual: boolean
  check_out_manual: boolean
  has_check_in_snapshot: boolean
  has_check_out_snapshot: boolean
  late_minutes: number
  early_minutes: number
  status: string
  note: string
  detail: string
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const people = ref<Person[]>([])
const departments = ref<Department[]>([])
const rows = ref<Row[]>([])
const loading = ref(true)
const error = ref('')
const employeeId = ref('')
const departmentId = ref('')
const status = ref('')
const fromDate = ref(today())
const toDate = ref(today())
const filtersOpen = ref(false)
const correcting = ref('')
const checkIn = ref('')
const checkOut = ref('')
const note = ref('')
const saving = ref(false)
const correctError = ref('')
const corrections = ref<Fix[]>([])
const fixDate = ref(today())
const fixIn = ref('')
const fixOut = ref('')
const fixNote = ref('')
const fixError = ref('')
const fixNotice = ref('')
const fixSaving = ref(false)
const fixBusy = ref<number | null>(null)

type Fix = {
  id: number
  employee_name: string
  local_date: string
  check_in: string | null
  check_out: string | null
  note: string
  status: string
}

const mine = computed(() => route.path === '/me' || auth.me?.role === 'employee')
const canCorrect = computed(() => !mine.value)
const exportHref = computed(() => {
  const params = new URLSearchParams()
  if (mine.value && auth.me?.employee_id) params.set('employee_id', String(auth.me.employee_id))
  else if (employeeId.value) params.set('employee_id', employeeId.value)
  if (!mine.value && departmentId.value) params.set('department_id', departmentId.value)
  if (status.value) params.set('status', status.value)
  if (fromDate.value) params.set('from', fromDate.value)
  if (toDate.value) params.set('to', toDate.value)
  return `/api/attendance/export?${params}`
})

const ranges = [
  { key: 'today', label: 'Today' },
  { key: 'week', label: 'This week' },
  { key: 'month', label: 'This month' },
] as const

const statuses = [
  ['due', 'Not in yet'],
  ['present', 'Present'],
  ['late', 'Late'],
  ['left_early', 'Left early'],
  ['incomplete', 'Incomplete'],
  ['absent', 'Absent'],
  ['on_leave', 'On leave'],
  ['holiday', 'Holiday'],
] as const

const activeRange = computed(() => {
  if (toDate.value !== today()) return ''
  if (fromDate.value === today()) return 'today'
  if (fromDate.value === weekStart()) return 'week'
  if (fromDate.value === monthStart()) return 'month'
  return ''
})

const activeFilters = computed(
  () => [employeeId.value, departmentId.value, status.value].filter(Boolean).length,
)

const summary = computed(() => {
  const count = (keys: string[]) => rows.value.filter((row) => keys.includes(row.status)).length
  return [
    { label: 'On time', value: count(['present']) },
    { label: 'Late', value: rows.value.filter((row) => row.late_minutes > 0).length, tone: 'warn' },
    { label: 'Absent', value: count(['absent']), tone: 'danger' },
    { label: 'On leave', value: count(['on_leave']) },
  ]
})

function setRange(key: string) {
  toDate.value = today()
  if (key === 'today') fromDate.value = today()
  if (key === 'week') fromDate.value = weekStart()
  if (key === 'month') fromDate.value = monthStart()
}

function clearFilters() {
  employeeId.value = ''
  departmentId.value = ''
  status.value = ''
}

function fail(err: unknown) {
  if (unauthorized(err)) {
    router.push('/login')
    return true
  }
  return false
}

function keyOf(row: Row) {
  return `${row.employee_id ?? 'x'}-${row.local_date}`
}

function snapshot(row: Row, which: 'in' | 'out') {
  const has = which === 'in' ? row.has_check_in_snapshot : row.has_check_out_snapshot
  return has && row.id ? `/api/attendance/${row.id}/snapshot?which=${which}` : null
}

function offBy(row: Row) {
  const parts = []
  if (row.late_minutes) parts.push(`${minutes(row.late_minutes)} late`)
  if (row.early_minutes) parts.push(`${minutes(row.early_minutes)} early`)
  return parts.join(' · ')
}

async function loadFilters() {
  if (mine.value) return
  const [roster, groups] = await Promise.all([api<Person[]>('/api/employees'), api<Department[]>('/api/departments')])
  people.value = roster
  departments.value = groups
}

function clockOrDash(value: string | null) {
  return value || '—'
}

async function loadCorrections() {
  const path = mine.value ? '/api/corrections' : '/api/corrections?status=pending'
  try {
    corrections.value = await api<Fix[]>(path)
  } catch (err) {
    if (!fail(err)) fixError.value = errorText(err)
  }
}

async function sendCorrection() {
  fixError.value = ''
  fixNotice.value = ''
  if (!fixIn.value && !fixOut.value) {
    fixError.value = 'Enter a check-in or a check-out time.'
    return
  }
  fixSaving.value = true
  try {
    await api('/api/corrections', {
      method: 'POST',
      body: JSON.stringify({
        local_date: fixDate.value,
        check_in: fixIn.value || null,
        check_out: fixOut.value || null,
        note: fixNote.value,
      }),
    })
    fixIn.value = ''
    fixOut.value = ''
    fixNote.value = ''
    fixNotice.value = 'Request sent. An admin will review it.'
    await loadCorrections()
  } catch (err) {
    if (!fail(err)) fixError.value = errorText(err)
  } finally {
    fixSaving.value = false
  }
}

async function reviewFix(row: Fix, decision: 'approve' | 'reject') {
  fixBusy.value = row.id
  fixError.value = ''
  try {
    await api(`/api/corrections/${row.id}/${decision}`, { method: 'POST' })
    await Promise.all([loadCorrections(), loadAttendance()])
    window.dispatchEvent(new Event('badges-refresh'))
  } catch (err) {
    if (!fail(err)) fixError.value = errorText(err)
  } finally {
    fixBusy.value = null
  }
}

async function loadAttendance() {
  loading.value = true
  error.value = ''
  if (mine.value && !auth.me?.employee_id) {
    rows.value = []
    loading.value = false
    return
  }
  const params = new URLSearchParams()
  if (mine.value && auth.me?.employee_id) params.set('employee_id', String(auth.me.employee_id))
  else if (employeeId.value) params.set('employee_id', employeeId.value)
  if (!mine.value && departmentId.value) params.set('department_id', departmentId.value)
  if (status.value) params.set('status', status.value)
  if (fromDate.value) params.set('from', fromDate.value)
  if (toDate.value) params.set('to', toDate.value)
  try {
    rows.value = await api<Row[]>(`/api/attendance?${params}`)
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    loading.value = false
  }
}

function startCorrect(row: Row) {
  if (correcting.value === keyOf(row)) {
    correcting.value = ''
    return
  }
  correcting.value = keyOf(row)
  correctError.value = ''
  checkIn.value = row.check_in_at ? formatTime(row.check_in_at) : ''
  checkOut.value = row.check_out_at ? formatTime(row.check_out_at) : ''
  note.value = ''
}

async function saveCorrect(row: Row) {
  if (!row.employee_id) return
  saving.value = true
  correctError.value = ''
  try {
    await api('/api/attendance/correct', {
      method: 'POST',
      body: JSON.stringify({
        employee_id: row.employee_id,
        local_date: row.local_date,
        check_in: checkIn.value || null,
        check_out: checkOut.value || null,
        note: note.value,
      }),
    })
    correcting.value = ''
    await loadAttendance()
  } catch (err) {
    if (!fail(err)) correctError.value = errorText(err)
  } finally {
    saving.value = false
  }
}

watch([employeeId, departmentId, status, fromDate, toDate], () => {
  void loadAttendance()
})

onMounted(async () => {
  if (mine.value) fromDate.value = monthStart()
  try {
    await loadFilters()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  }
  await Promise.all([loadAttendance(), loadCorrections()])
})
</script>

<template>
  <section class="space-y-5">
    <PageHeader
      :title="mine ? 'My attendance' : 'Attendance'"
      :subtitle="mine ? 'Your workdays, and a place to ask for a missed punch.' : 'Check-ins, check-outs, and days with no punch.'"
    >
      <a class="btn-quiet no-underline" :href="exportHref">Download CSV</a>
    </PageHeader>

    <form v-if="mine && auth.me?.employee_id" class="card card-pad space-y-4" @submit.prevent="sendCorrection">
      <p class="section-title">Request a correction</p>
      <p class="muted">Forgot to check in or out? Send the time and a reason. An admin approves it.</p>
      <div class="flex flex-wrap items-end gap-3">
        <label>
          <span class="field-label">Date</span>
          <input v-model="fixDate" class="field" type="date" :max="today()" required />
        </label>
        <label>
          <span class="field-label">Check in</span>
          <input v-model="fixIn" class="field" type="time" />
        </label>
        <label>
          <span class="field-label">Check out</span>
          <input v-model="fixOut" class="field" type="time" />
        </label>
        <label>
          <span class="field-label">Reason</span>
          <input v-model="fixNote" class="field" placeholder="What happened" required />
        </label>
        <button class="btn" type="submit" :disabled="fixSaving">{{ fixSaving ? 'Sending…' : 'Send request' }}</button>
      </div>
      <p v-if="fixError" class="error">{{ fixError }}</p>
      <p v-else-if="fixNotice" class="notice notice-good" role="status">{{ fixNotice }}</p>
    </form>

    <div v-if="mine && corrections.length" class="card">
      <div class="card-head !py-3">
        <p class="section-title">My requests</p>
        <span class="muted">{{ corrections.length }}</span>
      </div>
      <ul class="list">
        <li v-for="request in corrections" :key="request.id" class="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 py-3 text-sm">
          <span class="num min-w-0 flex-1">
            {{ formatDay(request.local_date) }} · in {{ clockOrDash(request.check_in) }} · out {{ clockOrDash(request.check_out) }}
            <span class="text-mute">· {{ request.note }}</span>
          </span>
          <StatusChip :status="request.status" />
        </li>
      </ul>
    </div>

    <div v-if="canCorrect && (corrections.length || fixError)" class="card">
      <div class="card-head !py-3">
        <p class="section-title">Correction requests</p>
        <span class="muted">{{ corrections.length }}</span>
      </div>
      <p v-if="fixError" class="error px-5 py-3">{{ fixError }}</p>
      <ul v-if="corrections.length" class="list">
        <li v-for="request in corrections" :key="request.id" class="flex flex-wrap items-center gap-x-4 gap-y-3 px-5 py-4">
          <div class="min-w-0 flex-1">
            <p class="truncate font-medium">{{ request.employee_name }}</p>
            <p class="num text-xs text-mute">
              {{ formatDay(request.local_date) }} · in {{ clockOrDash(request.check_in) }} · out {{ clockOrDash(request.check_out) }}
            </p>
            <p class="mt-1 text-sm text-mute">“{{ request.note }}”</p>
          </div>
          <div class="flex gap-2">
            <button class="btn btn-sm" type="button" :disabled="fixBusy === request.id" @click="reviewFix(request, 'approve')">Approve</button>
            <button class="btn-quiet btn-sm" type="button" :disabled="fixBusy === request.id" @click="reviewFix(request, 'reject')">Reject</button>
          </div>
        </li>
      </ul>
    </div>

    <div class="flex flex-wrap items-center gap-3">
      <div class="segmented" role="group" aria-label="Date range">
        <button
          v-for="range in ranges"
          :key="range.key"
          type="button"
          :aria-pressed="activeRange === range.key"
          @click="setRange(range.key)"
        >
          {{ range.label }}
        </button>
      </div>
      <div class="flex items-center gap-2">
        <input v-model="fromDate" class="field !h-9 w-40" type="date" aria-label="From" />
        <span class="muted">to</span>
        <input v-model="toDate" class="field !h-9 w-40" type="date" aria-label="To" />
      </div>
      <button
        v-if="!mine"
        class="btn-quiet md:hidden"
        type="button"
        :aria-expanded="filtersOpen"
        @click="filtersOpen = !filtersOpen"
      >
        Filters<span v-if="activeFilters"> · {{ activeFilters }}</span>
      </button>
    </div>

    <div v-if="!mine" class="toolbar" :class="filtersOpen ? 'flex' : 'hidden md:flex'">
      <label>
        <span class="field-label">Employee</span>
        <FieldSelect
          v-model="employeeId"
          :options="[{ value: '', label: 'Everyone' }, ...people.map((person) => ({ value: String(person.id), label: person.name }))]"
        />
      </label>
      <label v-if="departments.length">
        <span class="field-label">Department</span>
        <FieldSelect
          v-model="departmentId"
          :options="[{ value: '', label: 'All' }, ...departments.map((department) => ({ value: String(department.id), label: department.name }))]"
        />
      </label>
      <label>
        <span class="field-label">Status</span>
        <FieldSelect
          v-model="status"
          :options="[{ value: '', label: 'Any' }, ...statuses.map(([value, label]) => ({ value, label }))]"
        />
      </label>
      <button v-if="activeFilters" class="btn-link mb-2" type="button" @click="clearFilters">Clear filters</button>
    </div>

    <div v-if="mine && rows.length" class="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <div v-for="item in summary" :key="item.label" class="stat">
        <span
          class="stat-value"
          :class="{ 'text-warn': item.tone === 'warn' && item.value, 'text-danger': item.tone === 'danger' && item.value }"
        >
          {{ item.value }}
        </span>
        <span class="stat-label">{{ item.label }}</span>
      </div>
    </div>

    <p v-if="loading && rows.length === 0" class="muted">Loading…</p>
    <p v-else-if="error" class="notice notice-danger">{{ error }}</p>
    <div v-else-if="mine && !auth.me?.employee_id" class="card empty">
      <p class="section-title">No employee profile</p>
      <p class="muted">This login is not linked to an employee yet. Ask an admin.</p>
    </div>
    <div v-else-if="rows.length === 0" class="card empty">
      <p class="section-title">No workdays</p>
      <p class="muted">Nothing in this range. Try a wider range or clear the filters.</p>
    </div>
    <template v-else>
      <p class="muted">{{ rows.length }} {{ rows.length === 1 ? 'day' : 'days' }}</p>

      <div class="card hidden overflow-x-auto md:block">
        <table class="data-table min-w-[44rem]">
          <thead>
            <tr>
              <th v-if="!mine">Employee</th>
              <th>Date</th>
              <th>In</th>
              <th>Out</th>
              <th>Status</th>
              <th v-if="canCorrect"><span class="sr-only">Actions</span></th>
            </tr>
          </thead>
          <tbody>
            <template v-for="row in rows" :key="keyOf(row)">
              <tr>
                <td v-if="!mine" class="min-w-[12rem]">
                  <div class="flex items-center gap-3">
                    <a v-if="snapshot(row, 'in')" :href="snapshot(row, 'in')!" target="_blank" title="Check-in photo">
                      <UserAvatar :name="row.employee_name" :src="snapshot(row, 'in')" />
                    </a>
                    <UserAvatar v-else :name="row.employee_name" />
                    <div class="min-w-0">
                      <p class="truncate font-medium">{{ row.employee_name }}</p>
                      <p v-if="row.department" class="truncate text-xs text-mute">{{ row.department }}</p>
                    </div>
                  </div>
                </td>
                <td class="num">
                  <span class="text-mute">{{ weekday(row.local_date) }}</span> {{ formatDay(row.local_date) }}
                </td>
                <td class="num">
                  <a v-if="snapshot(row, 'in') && mine" :href="snapshot(row, 'in')!" target="_blank" class="underline decoration-line underline-offset-4">
                    {{ formatTime(row.check_in_at) }}
                  </a>
                  <template v-else>{{ formatTime(row.check_in_at) }}</template>
                  <span v-if="row.check_in_manual" class="tag">manual</span>
                </td>
                <td class="num">
                  <a v-if="snapshot(row, 'out')" :href="snapshot(row, 'out')!" target="_blank" class="underline decoration-line underline-offset-4" title="Check-out photo">
                    {{ formatTime(row.check_out_at) }}
                  </a>
                  <template v-else>{{ formatTime(row.check_out_at) }}</template>
                  <span v-if="row.check_out_manual" class="tag">manual</span>
                </td>
                <td>
                  <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <StatusChip :status="row.status" />
                    <span v-if="offBy(row)" class="text-xs text-mute">{{ offBy(row) }}</span>
                  </div>
                  <p v-if="row.note" class="mt-1 max-w-xs truncate text-xs text-mute" :title="row.note">Note: {{ row.note }}</p>
                </td>
                <td v-if="canCorrect" class="text-right">
                  <button v-if="row.employee_id" class="btn-link" type="button" @click="startCorrect(row)">
                    {{ correcting === keyOf(row) ? 'Cancel' : 'Correct' }}
                  </button>
                </td>
              </tr>
              <tr v-if="canCorrect && correcting === keyOf(row)">
                <td :colspan="mine ? 5 : 6" class="!bg-soft">
                  <form class="flex flex-wrap items-end gap-3 py-1" @submit.prevent="saveCorrect(row)">
                    <label class="w-32">
                      <span class="field-label">Check in</span>
                      <input v-model="checkIn" class="field" type="time" />
                    </label>
                    <label class="w-32">
                      <span class="field-label">Check out</span>
                      <input v-model="checkOut" class="field" type="time" />
                    </label>
                    <label class="min-w-56 flex-1">
                      <span class="field-label">Reason</span>
                      <input v-model="note" class="field" placeholder="Why this changed (required)" required />
                    </label>
                    <button class="btn" type="submit" :disabled="saving">{{ saving ? 'Saving…' : 'Save correction' }}</button>
                    <p v-if="correctError" class="error w-full">{{ correctError }}</p>
                  </form>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>

      <ul class="card list md:hidden">
        <li v-for="row in rows" :key="keyOf(row)" class="space-y-3 px-4 py-3.5">
          <div class="flex items-center gap-3">
            <UserAvatar :name="row.employee_name" :src="snapshot(row, 'in')" />
            <div class="min-w-0 flex-1">
              <p class="truncate font-medium">{{ mine ? `${weekday(row.local_date)} ${formatDay(row.local_date)}` : row.employee_name }}</p>
              <p class="text-xs text-mute">{{ mine ? row.department || '' : `${weekday(row.local_date)} ${formatDay(row.local_date)}` }}</p>
            </div>
            <StatusChip :status="row.status" />
          </div>
          <div class="grid grid-cols-3 gap-2 text-sm">
            <div>
              <p class="text-xs text-mute">In</p>
              <p class="num">{{ formatTime(row.check_in_at) }}<span v-if="row.check_in_manual" class="tag">m</span></p>
            </div>
            <div>
              <p class="text-xs text-mute">Out</p>
              <p class="num">{{ formatTime(row.check_out_at) }}<span v-if="row.check_out_manual" class="tag">m</span></p>
            </div>
            <div>
              <p class="text-xs text-mute">Off by</p>
              <p class="num">{{ offBy(row) || '—' }}</p>
            </div>
          </div>
          <p v-if="row.note" class="text-xs text-mute">Note: {{ row.note }}</p>
          <template v-if="canCorrect && row.employee_id">
            <button class="btn-quiet btn-sm" type="button" @click="startCorrect(row)">
              {{ correcting === keyOf(row) ? 'Cancel' : 'Correct' }}
            </button>
            <form v-if="correcting === keyOf(row)" class="grid grid-cols-2 gap-3" @submit.prevent="saveCorrect(row)">
              <label>
                <span class="field-label">Check in</span>
                <input v-model="checkIn" class="field" type="time" />
              </label>
              <label>
                <span class="field-label">Check out</span>
                <input v-model="checkOut" class="field" type="time" />
              </label>
              <label class="col-span-2">
                <span class="field-label">Reason</span>
                <input v-model="note" class="field" placeholder="Why this changed" required />
              </label>
              <p v-if="correctError" class="error col-span-2">{{ correctError }}</p>
              <button class="btn col-span-2" type="submit" :disabled="saving">{{ saving ? 'Saving…' : 'Save correction' }}</button>
            </form>
          </template>
        </li>
      </ul>
    </template>
  </section>
</template>
