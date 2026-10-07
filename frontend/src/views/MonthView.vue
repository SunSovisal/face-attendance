<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText, unauthorized } from '../api'
import FieldSelect from '../components/FieldSelect.vue'
import PageHeader from '../components/PageHeader.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { minutes, monthLabel, shiftMonth, thisMonth } from '../format'

type Department = { id: number; name: string }
type Row = {
  employee_id: number
  employee_name: string
  department: string
  present: number
  late: number
  incomplete: number
  absent: number
  leave: number
  late_minutes: number
}

const router = useRouter()
const departments = ref<Department[]>([])
const departmentId = ref('')
const month = ref(thisMonth())
const rows = ref<Row[]>([])
const loading = ref(true)
const error = ref('')

const totals = computed(() =>
  rows.value.reduce(
    (sum, row) => ({
      present: sum.present + row.present,
      late: sum.late + row.late,
      incomplete: sum.incomplete + row.incomplete,
      absent: sum.absent + row.absent,
      leave: sum.leave + row.leave,
    }),
    { present: 0, late: 0, incomplete: 0, absent: 0, leave: 0 },
  ),
)

const atLatest = computed(() => month.value >= thisMonth())
const exportHref = computed(() => {
  const params = new URLSearchParams({ month: month.value })
  if (departmentId.value) params.set('department_id', departmentId.value)
  return `/api/attendance/month/export?${params}`
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
  const params = new URLSearchParams({ month: month.value })
  if (departmentId.value) params.set('department_id', departmentId.value)
  try {
    const body = await api<{ rows: Row[] }>(`/api/attendance/month?${params}`)
    rows.value = body.rows
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    loading.value = false
  }
}

watch([month, departmentId], () => {
  void load()
})

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
    <PageHeader title="Month summary" subtitle="Days counted per employee, up to today.">
      <FieldSelect
        v-if="departments.length"
        v-model="departmentId"
        class="w-44"
        aria-label="Department"
        :options="[{ value: '', label: 'All departments' }, ...departments.map((department) => ({ value: String(department.id), label: department.name }))]"
      />
    </PageHeader>

    <div class="flex items-center gap-2">
      <button class="btn-quiet !px-3" type="button" aria-label="Previous month" @click="month = shiftMonth(month, -1)">‹</button>
      <label class="relative">
        <span class="sr-only">Month</span>
        <input v-model="month" class="field !h-9 w-44" type="month" :max="thisMonth()" />
      </label>
      <button class="btn-quiet !px-3" type="button" aria-label="Next month" :disabled="atLatest" @click="month = shiftMonth(month, 1)">›</button>
      <p class="section-title ml-2 hidden sm:block">{{ monthLabel(month) }}</p>
      <a class="btn-quiet ml-auto no-underline" :href="exportHref">Download CSV</a>
    </div>

    <div v-if="rows.length" class="grid grid-cols-2 gap-3 sm:grid-cols-5">
      <div class="stat"><span class="stat-value">{{ totals.present }}</span><span class="stat-label">Present days</span></div>
      <div class="stat"><span class="stat-value" :class="{ 'text-warn': totals.late }">{{ totals.late }}</span><span class="stat-label">Late days</span></div>
      <div class="stat"><span class="stat-value" :class="{ 'text-warn': totals.incomplete }">{{ totals.incomplete }}</span><span class="stat-label">Incomplete</span></div>
      <div class="stat"><span class="stat-value" :class="{ 'text-danger': totals.absent }">{{ totals.absent }}</span><span class="stat-label">Absences</span></div>
      <div class="stat"><span class="stat-value">{{ totals.leave }}</span><span class="stat-label">Leave days</span></div>
    </div>

    <p v-if="loading && rows.length === 0" class="muted">Loading…</p>
    <p v-else-if="error" class="notice notice-danger">{{ error }}</p>
    <div v-else-if="rows.length === 0" class="card empty">
      <p class="section-title">No employees</p>
      <p class="muted">Nobody is in this view for {{ monthLabel(month) }}.</p>
    </div>
    <template v-else>
      <div class="card hidden overflow-x-auto md:block">
        <table class="data-table min-w-[44rem]">
          <thead>
            <tr>
              <th>Employee</th>
              <th class="text-right">Present</th>
              <th class="text-right">Late</th>
              <th class="text-right">Incomplete</th>
              <th class="text-right">Absent</th>
              <th class="text-right">Leave</th>
              <th class="text-right">Late time</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rows" :key="row.employee_id">
              <td>
                <div class="flex items-center gap-3">
                  <UserAvatar :name="row.employee_name" />
                  <div class="min-w-0">
                    <p class="truncate font-medium">{{ row.employee_name }}</p>
                    <p v-if="row.department" class="truncate text-xs text-mute">{{ row.department }}</p>
                  </div>
                </div>
              </td>
              <td class="num text-right">{{ row.present }}</td>
              <td class="num text-right" :class="row.late ? 'font-medium text-warn' : 'text-mute'">{{ row.late }}</td>
              <td class="num text-right" :class="row.incomplete ? 'font-medium text-warn' : 'text-mute'">{{ row.incomplete }}</td>
              <td class="num text-right" :class="row.absent ? 'font-medium text-danger' : 'text-mute'">{{ row.absent }}</td>
              <td class="num text-right text-mute">{{ row.leave }}</td>
              <td class="num text-right text-mute">{{ minutes(row.late_minutes) }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <ul class="card list md:hidden">
        <li v-for="row in rows" :key="row.employee_id" class="space-y-3 px-4 py-3.5">
          <div class="flex items-center gap-3">
            <UserAvatar :name="row.employee_name" />
            <div class="min-w-0">
              <p class="truncate font-medium">{{ row.employee_name }}</p>
              <p class="text-xs text-mute">{{ row.department || 'No department' }}</p>
            </div>
          </div>
          <div class="grid grid-cols-5 gap-1 text-center">
            <div><p class="num font-medium">{{ row.present }}</p><p class="text-[0.7rem] text-mute">Present</p></div>
            <div><p class="num font-medium" :class="{ 'text-warn': row.late }">{{ row.late }}</p><p class="text-[0.7rem] text-mute">Late</p></div>
            <div><p class="num font-medium" :class="{ 'text-warn': row.incomplete }">{{ row.incomplete }}</p><p class="text-[0.7rem] text-mute">Incompl.</p></div>
            <div><p class="num font-medium" :class="{ 'text-danger': row.absent }">{{ row.absent }}</p><p class="text-[0.7rem] text-mute">Absent</p></div>
            <div><p class="num font-medium">{{ row.leave }}</p><p class="text-[0.7rem] text-mute">Leave</p></div>
          </div>
        </li>
      </ul>
    </template>
  </section>
</template>
