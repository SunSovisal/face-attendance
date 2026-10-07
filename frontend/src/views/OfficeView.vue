<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText, unauthorized } from '../api'
import PageHeader from '../components/PageHeader.vue'

const days = [
  ['mon', 'Mon'],
  ['tue', 'Tue'],
  ['wed', 'Wed'],
  ['thu', 'Thu'],
  ['fri', 'Fri'],
  ['sat', 'Sat'],
  ['sun', 'Sun'],
] as const

const router = useRouter()
const workStart = ref('08:00')
const workEnd = ref('17:00')
const grace = ref(10)
const weekend = ref<string[]>(['sat', 'sun'])
const loading = ref(true)
const saving = ref(false)
const error = ref('')
const notice = ref('')

const lateAfter = computed(() => {
  const [hour, minute] = workStart.value.split(':').map(Number)
  if (hour == null || minute == null || Number.isNaN(hour) || Number.isNaN(minute)) return workStart.value
  const total = hour * 60 + minute + (Number(grace.value) || 0)
  return `${String(Math.floor(total / 60) % 24).padStart(2, '0')}:${String(total % 60).padStart(2, '0')}`
})

const workdays = computed(() => days.filter(([value]) => !weekend.value.includes(value)).map(([, label]) => label))

function fail(err: unknown) {
  if (unauthorized(err)) {
    router.push('/login')
    return true
  }
  return false
}

onMounted(async () => {
  try {
    const office = await api<{ work_start: string; work_end: string; grace_minutes: number; weekend_days: string[] }>('/api/office')
    workStart.value = office.work_start
    workEnd.value = office.work_end
    grace.value = office.grace_minutes
    weekend.value = office.weekend_days
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    loading.value = false
  }
})

function toggleWorkday(day: string) {
  notice.value = ''
  weekend.value = weekend.value.includes(day) ? weekend.value.filter((item) => item !== day) : [...weekend.value, day]
}

async function save() {
  saving.value = true
  error.value = ''
  notice.value = ''
  try {
    await api('/api/office', {
      method: 'PUT',
      body: JSON.stringify({
        work_start: workStart.value,
        work_end: workEnd.value,
        grace_minutes: Number(grace.value),
        weekend_days: weekend.value,
      }),
    })
    notice.value = 'Office hours saved. New punches use these rules.'
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="space-y-6">
    <PageHeader title="Office hours" subtitle="One schedule for the whole roster." />
    <p v-if="loading" class="muted">Loading…</p>
    <div v-else class="grid max-w-[34rem] items-start gap-6 xl:max-w-none xl:grid-cols-[34rem_minmax(0,22rem)]">
      <form class="card card-pad space-y-6" @submit.prevent="save">
        <div class="grid gap-4 sm:grid-cols-3">
          <label>
            <span class="field-label">Start</span>
            <input v-model="workStart" class="field" type="time" required />
          </label>
          <label>
            <span class="field-label">End</span>
            <input v-model="workEnd" class="field" type="time" required />
          </label>
          <label>
            <span class="field-label">Grace (min)</span>
            <input v-model.number="grace" class="field" type="number" min="0" max="180" />
          </label>
        </div>
        <fieldset>
          <legend class="field-label">Workdays</legend>
          <div class="mt-1 flex flex-wrap gap-2">
            <button
              v-for="[value, label] in days"
              :key="value"
              class="day-toggle"
              type="button"
              :aria-pressed="!weekend.includes(value)"
              @click="toggleWorkday(value)"
            >
              {{ label }}
            </button>
          </div>
          <p class="hint">Unselected days are days off. Nobody is expected in.</p>
        </fieldset>
        <p v-if="error" class="notice notice-danger">{{ error }}</p>
        <p v-else-if="notice" class="notice notice-good" role="status">{{ notice }}</p>
        <button class="btn" type="submit" :disabled="saving">{{ saving ? 'Saving…' : 'Save hours' }}</button>
      </form>

      <aside class="card card-pad space-y-3">
        <p class="field-label !mb-0">How a day is judged</p>
        <ul class="space-y-2.5 text-sm">
          <li class="grid grid-cols-[5.5rem_1fr] items-center gap-3"><span class="chip chip-good justify-self-start">On time</span><span class="muted">Check in by {{ lateAfter }}</span></li>
          <li class="grid grid-cols-[5.5rem_1fr] items-center gap-3"><span class="chip chip-warn justify-self-start">Late</span><span class="muted">Check in after {{ lateAfter }}</span></li>
          <li class="grid grid-cols-[5.5rem_1fr] items-center gap-3"><span class="chip chip-warn justify-self-start">Left early</span><span class="muted">Check out before {{ workEnd }}</span></li>
          <li class="grid grid-cols-[5.5rem_1fr] items-center gap-3"><span class="chip chip-danger justify-self-start">Absent</span><span class="muted">No punch on a workday without leave</span></li>
        </ul>
        <p class="muted border-t border-line pt-3">
          Working {{ workdays.length ? workdays.join(', ') : 'no days' }}.
        </p>
      </aside>
    </div>
  </section>
</template>
