<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText, unauthorized } from '../api'
import PageHeader from '../components/PageHeader.vue'
import { formatDay, today, weekday } from '../format'

type Holiday = { id: number; local_date: string; name: string }

const router = useRouter()
const rows = ref<Holiday[]>([])
const loading = ref(true)
const error = ref('')
const formError = ref('')
const name = ref('')
const localDate = ref(today())
const saving = ref(false)

const upcoming = computed(() =>
  rows.value.filter((row) => row.local_date >= today()).sort((a, b) => a.local_date.localeCompare(b.local_date)),
)
const past = computed(() => rows.value.filter((row) => row.local_date < today()))

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
    rows.value = await api<Holiday[]>('/api/holidays')
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    loading.value = false
  }
}

async function addHoliday() {
  formError.value = ''
  if (!name.value.trim()) {
    formError.value = 'Give the holiday a name.'
    return
  }
  saving.value = true
  try {
    await api('/api/holidays', {
      method: 'POST',
      body: JSON.stringify({ local_date: localDate.value, name: name.value.trim() }),
    })
    name.value = ''
    await load()
  } catch (err) {
    if (!fail(err)) formError.value = errorText(err)
  } finally {
    saving.value = false
  }
}

async function remove(row: Holiday) {
  if (!window.confirm(`Remove ${row.name} on ${formatDay(row.local_date)}?`)) return
  try {
    await api(`/api/holidays/${row.id}`, { method: 'DELETE' })
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  }
}

onMounted(load)
</script>

<template>
  <section class="space-y-6">
    <PageHeader title="Holidays" subtitle="The whole office is closed on these dates. Nobody is marked absent." />

    <form class="card card-pad flex flex-wrap items-end gap-3" @submit.prevent="addHoliday">
      <label class="w-44">
        <span class="field-label">Date</span>
        <input v-model="localDate" class="field" type="date" required />
      </label>
      <label class="min-w-56 flex-1">
        <span class="field-label">Name</span>
        <input v-model="name" class="field" placeholder="e.g. Khmer New Year" />
      </label>
      <button class="btn" type="submit" :disabled="saving">{{ saving ? 'Adding…' : 'Add holiday' }}</button>
      <p v-if="formError" class="error w-full">{{ formError }}</p>
    </form>

    <p v-if="error" class="notice notice-danger">{{ error }}</p>
    <p v-if="loading" class="muted">Loading…</p>
    <div v-else-if="rows.length === 0" class="card empty">
      <p class="section-title">No holidays yet</p>
      <p class="muted">Add public holidays so they never count as absences.</p>
    </div>
    <template v-else>
      <div v-for="group in [{ label: 'Upcoming', items: upcoming }, { label: 'Past', items: past }]" :key="group.label">
        <div v-if="group.items.length" class="card">
          <div class="card-head !py-3">
            <p class="section-title">{{ group.label }}</p>
            <span class="muted">{{ group.items.length }}</span>
          </div>
          <ul class="list">
            <li
              v-for="row in group.items"
              :key="row.id"
              class="flex items-center gap-4 px-5 py-3"
              :class="{ 'opacity-60': group.label === 'Past' }"
            >
              <div class="w-14 shrink-0 text-center">
                <p class="text-xs uppercase text-mute">{{ weekday(row.local_date) }}</p>
                <p class="num font-semibold">{{ formatDay(row.local_date) }}</p>
              </div>
              <p class="min-w-0 flex-1 truncate font-medium">{{ row.name }}</p>
              <button class="btn-danger btn-sm" type="button" :aria-label="`Delete ${row.name}`" @click="remove(row)">Delete</button>
            </li>
          </ul>
        </div>
      </div>
    </template>
  </section>
</template>
