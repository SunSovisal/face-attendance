<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText, unauthorized } from '../api'
import FieldSelect from '../components/FieldSelect.vue'
import PageHeader from '../components/PageHeader.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { roleLabel } from '../format'
import { useAuthStore } from '../stores/auth'

type Department = { id: number; name: string }
type Employee = {
  id: number
  name: string
  employee_code: string | null
  position: string
  status: string
  department_id: number | null
  department_name: string
  sample_count: number
  photos: number[]
  username: string | null
  role: string | null
  account_status: string | null
}

const router = useRouter()
const auth = useAuthStore()
const superAdmin = computed(() => auth.me?.role === 'super_admin')
const missingPhotos = ref(new Set<number>())
const people = ref<Employee[]>([])
const departments = ref<Department[]>([])
const loading = ref(true)
const error = ref('')
const formError = ref('')
const saving = ref(false)
const busyId = ref<number | null>(null)
const uploadingId = ref<number | null>(null)
const editingId = ref<number | null>(null)
const loginId = ref<number | null>(null)

const name = ref('')
const code = ref('')
const position = ref('')
const departmentId = ref('')
const photo = ref<File | null>(null)
const photoInput = ref<HTMLInputElement | null>(null)
const departmentName = ref('')

const editName = ref('')
const editCode = ref('')
const editPosition = ref('')
const editDepartmentId = ref('')
const editStatus = ref('active')
const loginUsername = ref('')
const loginPassword = ref('')
const passwordId = ref<number | null>(null)
const nextPassword = ref('')
const confirmPassword = ref('')
const notice = ref('')
const addOpen = ref(false)
const query = ref('')
const view = ref('all')

const counts = computed(() => ({
  all: people.value.length,
  pending: people.value.filter((person) => person.account_status === 'pending').length,
  photo: people.value.filter((person) => person.sample_count === 0).length,
  inactive: people.value.filter((person) => person.status !== 'active').length,
}))

const views = computed(() => [
  { key: 'all', label: 'All', count: counts.value.all },
  { key: 'pending', label: 'Awaiting approval', count: counts.value.pending },
  { key: 'photo', label: 'Needs photo', count: counts.value.photo },
  { key: 'inactive', label: 'Inactive', count: counts.value.inactive },
])

const shown = computed(() => {
  const term = query.value.trim().toLowerCase()
  return people.value.filter((person) => {
    if (view.value === 'pending' && person.account_status !== 'pending') return false
    if (view.value === 'photo' && person.sample_count !== 0) return false
    if (view.value === 'inactive' && person.status === 'active') return false
    if (!term) return true
    return [person.name, person.employee_code ?? '', person.position, person.department_name, person.username ?? '']
      .some((value) => value.toLowerCase().includes(term))
  })
})

function canSetPassword(person: Employee) {
  if (!person.username || person.role === 'super_admin') return false
  if (person.role === 'admin') return superAdmin.value
  return true
}

function meta(person: Employee) {
  return [person.employee_code, person.position, person.department_name].filter(Boolean).join(' · ') || 'No details yet'
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
    const [roster, groups] = await Promise.all([
      api<Employee[]>('/api/employees'),
      api<Department[]>('/api/departments'),
    ])
    people.value = roster
    departments.value = groups
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    loading.value = false
  }
}

function onPhotoChange(event: Event) {
  const input = event.target as HTMLInputElement
  photo.value = input.files?.[0] ?? null
}

async function createPerson() {
  formError.value = ''
  if (!name.value.trim()) {
    formError.value = 'Name is required'
    return
  }
  const body = new FormData()
  body.append('name', name.value.trim())
  body.append('employee_code', code.value.trim())
  body.append('position', position.value.trim())
  body.append('department_id', departmentId.value)
  if (photo.value) body.append('photo', photo.value)
  saving.value = true
  try {
    await api('/api/employees', { method: 'POST', body })
    name.value = ''
    code.value = ''
    position.value = ''
    departmentId.value = ''
    photo.value = null
    if (photoInput.value) photoInput.value.value = ''
    addOpen.value = false
    await load()
  } catch (err) {
    if (!fail(err)) formError.value = errorText(err)
  } finally {
    saving.value = false
  }
}

async function addDepartment() {
  error.value = ''
  if (!departmentName.value.trim()) return
  try {
    await api('/api/departments', {
      method: 'POST',
      body: JSON.stringify({ name: departmentName.value.trim() }),
    })
    departmentName.value = ''
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  }
}

async function removeDepartment(department: Department) {
  if (!window.confirm(`Delete ${department.name}?`)) return
  try {
    await api(`/api/departments/${department.id}`, { method: 'DELETE' })
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  }
}

function startLogin(person: Employee) {
  editingId.value = null
  passwordId.value = null
  loginId.value = loginId.value === person.id ? null : person.id
  loginUsername.value = ''
  loginPassword.value = ''
}

function startEdit(person: Employee) {
  if (editingId.value === person.id) {
    editingId.value = null
    return
  }
  editingId.value = person.id
  loginId.value = null
  editName.value = person.name
  editCode.value = person.employee_code ?? ''
  editPosition.value = person.position
  editDepartmentId.value = person.department_id ? String(person.department_id) : ''
  editStatus.value = person.status
}

async function saveEdit(person: Employee) {
  busyId.value = person.id
  error.value = ''
  try {
    await api(`/api/employees/${person.id}`, {
      method: 'PATCH',
      body: JSON.stringify({
        name: editName.value.trim(),
        employee_code: editCode.value.trim(),
        position: editPosition.value.trim(),
        department_id: editDepartmentId.value ? Number(editDepartmentId.value) : null,
        status: editStatus.value,
      }),
    })
    editingId.value = null
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    busyId.value = null
  }
}

async function addPhoto(personId: number, event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  error.value = ''
  busyId.value = personId
  uploadingId.value = personId
  const body = new FormData()
  body.append('photo', file)
  try {
    await api(`/api/employees/${personId}/photos`, { method: 'POST', body })
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    busyId.value = null
    uploadingId.value = null
  }
}

function markMissing(photoId: number) {
  missingPhotos.value = new Set(missingPhotos.value).add(photoId)
}

async function removePhoto(person: Employee, photoId: number) {
  if (!window.confirm(`Delete this photo of ${person.name}?`)) return
  busyId.value = person.id
  error.value = ''
  try {
    await api(`/api/employees/${person.id}/photos/${photoId}`, { method: 'DELETE' })
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    busyId.value = null
  }
}

async function activate(person: Employee) {
  busyId.value = person.id
  error.value = ''
  try {
    await api(`/api/employees/${person.id}/activate`, { method: 'POST' })
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    busyId.value = null
  }
}

function startPassword(person: Employee) {
  passwordId.value = passwordId.value === person.id ? null : person.id
  loginId.value = null
  nextPassword.value = ''
  confirmPassword.value = ''
  error.value = ''
}

async function savePassword(person: Employee) {
  error.value = ''
  notice.value = ''
  if (nextPassword.value !== confirmPassword.value) {
    error.value = 'The passwords do not match.'
    return
  }
  busyId.value = person.id
  try {
    await api(`/api/employees/${person.id}/password`, {
      method: 'POST',
      body: JSON.stringify({ password: nextPassword.value }),
    })
    notice.value = `Password updated for ${person.name}. Tell them the new one.`
    passwordId.value = null
    nextPassword.value = ''
    confirmPassword.value = ''
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    busyId.value = null
  }
}

async function createLogin(person: Employee) {
  busyId.value = person.id
  error.value = ''
  try {
    await api(`/api/employees/${person.id}/account`, {
      method: 'POST',
      body: JSON.stringify({ username: loginUsername.value.trim(), password: loginPassword.value }),
    })
    loginId.value = null
    loginUsername.value = ''
    loginPassword.value = ''
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    busyId.value = null
  }
}

async function removePerson(person: Employee) {
  if (!window.confirm(`Delete ${person.name}?`)) return
  busyId.value = person.id
  error.value = ''
  try {
    await api(`/api/employees/${person.id}`, { method: 'DELETE' })
    await load()
  } catch (err) {
    if (!fail(err)) error.value = errorText(err)
  } finally {
    busyId.value = null
  }
}

onMounted(async () => {
  await load()
  if (people.value.length === 0) addOpen.value = true
  else if (counts.value.pending) view.value = 'pending'
})
</script>

<template>
  <section class="space-y-6">
    <PageHeader title="Employees" subtitle="The roster the camera can recognize. Each photo needs exactly one face.">
      <button class="btn" type="button" :aria-expanded="addOpen" @click="addOpen = !addOpen">
        {{ addOpen ? 'Close' : 'Add employee' }}
      </button>
    </PageHeader>

    <form v-if="addOpen" class="card card-pad space-y-5" @submit.prevent="createPerson">
      <p class="section-title">New employee</p>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <label>
          <span class="field-label">Name</span>
          <input v-model="name" class="field" autocomplete="off" placeholder="Full name" required />
        </label>
        <label>
          <span class="field-label">Employee code</span>
          <input v-model="code" class="field" autocomplete="off" placeholder="Optional" />
        </label>
        <label>
          <span class="field-label">Position</span>
          <input v-model="position" class="field" autocomplete="off" placeholder="Optional" />
        </label>
        <label>
          <span class="field-label">Department</span>
          <FieldSelect
            v-model="departmentId"
            :options="[{ value: '', label: 'None' }, ...departments.map((department) => ({ value: String(department.id), label: department.name }))]"
          />
        </label>
        <label class="sm:col-span-2 lg:col-span-4">
          <span class="field-label">Face photo</span>
          <input ref="photoInput" class="file" type="file" accept="image/*" @change="onPhotoChange" />
          <p class="hint">One clear, front-facing photo with a single face. You can add more later.</p>
        </label>
      </div>
      <p v-if="formError" class="error">{{ formError }}</p>
      <div class="flex gap-2">
        <button class="btn" type="submit" :disabled="saving">{{ saving ? 'Adding…' : 'Add employee' }}</button>
        <button class="btn-quiet" type="button" @click="addOpen = false">Cancel</button>
      </div>
    </form>

    <div class="grid items-start gap-6 xl:grid-cols-[minmax(0,1fr)_17rem]">
      <div class="min-w-0 space-y-4">
        <div class="flex flex-wrap items-center gap-3">
          <input v-model="query" class="field max-w-xs !h-9" type="search" placeholder="Search name, code, position…" aria-label="Search" />
          <div class="segmented" role="group" aria-label="Show">
            <button v-for="item in views" :key="item.key" type="button" :aria-pressed="view === item.key" @click="view = item.key">
              {{ item.label }} <span class="opacity-60">{{ item.count }}</span>
            </button>
          </div>
        </div>

        <p v-if="notice" class="notice notice-good" role="status">{{ notice }}</p>
        <p v-if="error" class="notice notice-danger">{{ error }}</p>
        <p v-if="loading && people.length === 0" class="muted">Loading…</p>
        <div v-else-if="people.length === 0" class="card empty">
          <p class="section-title">No employees yet</p>
          <p class="muted">Add someone, or let people register and approve them here.</p>
        </div>
        <div v-else-if="shown.length === 0" class="card empty">
          <p class="section-title">No matches</p>
          <p class="muted">Nobody matches this search or filter.</p>
        </div>

        <ul v-else class="card list">
          <li v-for="person in shown" :key="person.id" class="px-5 py-4">
            <div class="flex flex-wrap items-center gap-x-4 gap-y-3">
              <div class="flex min-w-0 flex-1 basis-60 items-center gap-3">
                <UserAvatar :name="person.name" />
                <div class="min-w-0">
                  <p class="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span class="truncate font-medium">{{ person.name }}</span>
                    <span v-if="person.role && person.role !== 'employee'" class="chip chip-neutral">{{ roleLabel(person.role) }}</span>
                  </p>
                  <p class="truncate text-xs text-mute">{{ meta(person) }}</p>
                </div>
              </div>

              <div class="flex flex-wrap items-center gap-2">
                <span v-if="person.account_status === 'pending'" class="chip chip-warn">Awaiting approval</span>
                <span v-if="person.status !== 'active'" class="chip">Inactive</span>
                <span v-if="person.sample_count === 0" class="chip chip-warn">Needs photo</span>
                <span v-else class="chip">{{ person.sample_count }} photo{{ person.sample_count === 1 ? '' : 's' }}</span>
                <span v-if="person.username" class="chip" :title="`Login: ${person.username}`">@{{ person.username }}</span>
              </div>

              <div class="flex flex-wrap items-center gap-1.5">
                <button
                  v-if="person.account_status === 'pending'"
                  class="btn btn-sm"
                  type="button"
                  :disabled="busyId === person.id"
                  @click="activate(person)"
                >
                  Approve
                </button>
                <label class="btn-quiet btn-sm" :class="{ 'opacity-40': busyId === person.id }">
                  {{ uploadingId === person.id ? 'Uploading…' : 'Add photo' }}
                  <input class="sr-only" type="file" accept="image/*" :disabled="busyId === person.id" @change="addPhoto(person.id, $event)" />
                </label>
                <button class="btn-quiet btn-sm" type="button" :aria-expanded="editingId === person.id" @click="startEdit(person)">Edit</button>
                <button
                  v-if="!person.username"
                  class="btn-quiet btn-sm"
                  type="button"
                  :aria-expanded="loginId === person.id"
                  @click="startLogin(person)"
                >
                  Create login
                </button>
                <button
                  v-if="canSetPassword(person)"
                  class="btn-quiet btn-sm"
                  type="button"
                  :aria-expanded="passwordId === person.id"
                  @click="startPassword(person)"
                >
                  Set password
                </button>
                <button
                  v-if="person.role !== 'super_admin'"
                  class="btn-danger btn-sm"
                  type="button"
                  :disabled="busyId === person.id"
                  @click="removePerson(person)"
                >
                  Delete
                </button>
              </div>
            </div>

            <div v-if="superAdmin && person.photos.length" class="mt-4 flex flex-wrap gap-3">
              <figure v-for="photoId in person.photos" :key="photoId" class="w-24">
                <img
                  v-if="!missingPhotos.has(photoId)"
                  :src="`/api/employees/${person.id}/photos/${photoId}`"
                  :alt="`${person.name} photo`"
                  class="aspect-[3/4] w-full rounded-xl bg-soft object-cover object-top"
                  @error="markMissing(photoId)"
                />
                <div v-else class="grid aspect-[3/4] w-full place-items-center rounded-xl bg-soft px-2 text-center text-xs text-mute">
                  File missing
                </div>
                <button
                  class="btn-danger btn-sm mt-1.5 w-full"
                  type="button"
                  :disabled="busyId === person.id"
                  :aria-label="`Delete photo of ${person.name}`"
                  @click="removePhoto(person, photoId)"
                >
                  Delete
                </button>
              </figure>
            </div>

            <form
              v-if="editingId === person.id"
              class="mt-4 grid gap-4 rounded-xl bg-soft p-4 sm:grid-cols-2 lg:grid-cols-3"
              @submit.prevent="saveEdit(person)"
            >
              <label>
                <span class="field-label">Name</span>
                <input v-model="editName" class="field" required />
              </label>
              <label>
                <span class="field-label">Employee code</span>
                <input v-model="editCode" class="field" />
              </label>
              <label>
                <span class="field-label">Position</span>
                <input v-model="editPosition" class="field" />
              </label>
              <label>
                <span class="field-label">Department</span>
                <FieldSelect
                  v-model="editDepartmentId"
                  :options="[{ value: '', label: 'None' }, ...departments.map((department) => ({ value: String(department.id), label: department.name }))]"
                />
              </label>
              <label>
                <span class="field-label">Status</span>
                <FieldSelect
                  v-model="editStatus"
                  :options="[
                    { value: 'active', label: 'Active' },
                    { value: 'inactive', label: 'Inactive' },
                  ]"
                />
              </label>
              <div class="flex items-end gap-2">
                <button class="btn" type="submit" :disabled="busyId === person.id">Save</button>
                <button class="btn-quiet" type="button" @click="editingId = null">Cancel</button>
              </div>
            </form>

            <form
              v-if="loginId === person.id"
              class="mt-4 grid gap-4 rounded-xl bg-soft p-4 sm:grid-cols-[1fr_1fr_auto]"
              @submit.prevent="createLogin(person)"
            >
              <label>
                <span class="field-label">Username</span>
                <input v-model="loginUsername" class="field" autocomplete="off" required />
              </label>
              <label>
                <span class="field-label">Password</span>
                <input v-model="loginPassword" class="field" type="password" autocomplete="new-password" minlength="8" required />
              </label>
              <div class="flex items-end gap-2">
                <button class="btn" type="submit" :disabled="busyId === person.id">Create login</button>
                <button class="btn-quiet" type="button" @click="loginId = null">Cancel</button>
              </div>
              <p class="hint sm:col-span-3 !mt-0">At least 8 characters. They can sign in right away as an employee.</p>
            </form>

            <form
              v-if="passwordId === person.id"
              class="mt-4 grid gap-4 rounded-xl bg-soft p-4 sm:grid-cols-[1fr_1fr_auto]"
              @submit.prevent="savePassword(person)"
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
                <button class="btn" type="submit" :disabled="busyId === person.id">Save</button>
                <button class="btn-quiet" type="button" @click="passwordId = null">Cancel</button>
              </div>
              <p class="hint sm:col-span-3 !mt-0">At least 8 characters. Tell them the new password. Their old one stops working.</p>
            </form>
          </li>
        </ul>
      </div>

      <aside class="card max-w-md xl:max-w-none">
        <div class="card-head !py-3">
          <p class="section-title">Departments</p>
          <span class="muted">{{ departments.length }}</span>
        </div>
        <ul v-if="departments.length" class="list">
          <li v-for="department in departments" :key="department.id" class="flex items-center gap-2 px-5 py-2">
            <span class="min-w-0 flex-1 truncate text-sm">{{ department.name }}</span>
            <button
              class="btn-danger btn-sm !px-2"
              type="button"
              :aria-label="`Delete ${department.name}`"
              @click="removeDepartment(department)"
            >
              ×
            </button>
          </li>
        </ul>
        <p v-else class="muted px-5 py-3">No departments yet.</p>
        <form class="flex gap-2 border-t border-line p-3" @submit.prevent="addDepartment">
          <input v-model="departmentName" class="field !h-9" placeholder="New department" aria-label="New department" />
          <button class="btn btn-sm" type="submit" :disabled="!departmentName.trim()">Add</button>
        </form>
      </aside>
    </div>
  </section>
</template>

