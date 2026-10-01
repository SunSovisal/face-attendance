<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

type Person = {
  id: number
  name: string
  sample_count: number
  created_at: string | null
}

const router = useRouter()
const people = ref<Person[]>([])
const loading = ref(true)
const loadError = ref('')
const name = ref('')
const photo = ref<File | null>(null)
const photoInput = ref<HTMLInputElement | null>(null)
const formError = ref('')
const saving = ref(false)
const rowError = ref('')
const busyId = ref<number | null>(null)

async function errorMessage(response: Response) {
  if (response.status === 401) {
    router.push('/login')
    return 'Not signed in'
  }
  try {
    const body = await response.json()
    if (typeof body.detail === 'string') return body.detail
  } catch {
    // The body was not JSON.
  }
  return 'Request failed'
}

async function loadPeople() {
  loading.value = true
  loadError.value = ''
  const response = await fetch('/api/people', { credentials: 'include' })
  if (!response.ok) {
    loadError.value = await errorMessage(response)
    loading.value = false
    return
  }
  people.value = await response.json()
  loading.value = false
}

function onPhotoChange(event: Event) {
  const input = event.target as HTMLInputElement
  photo.value = input.files?.[0] ?? null
}

async function createPerson() {
  formError.value = ''
  if (!name.value.trim() || !photo.value) {
    formError.value = 'Name and a photo are required'
    return
  }
  const body = new FormData()
  body.append('name', name.value.trim())
  body.append('photo', photo.value)
  saving.value = true
  const response = await fetch('/api/people', {
    method: 'POST',
    credentials: 'include',
    body,
  })
  saving.value = false
  if (!response.ok) {
    formError.value = await errorMessage(response)
    return
  }
  name.value = ''
  photo.value = null
  if (photoInput.value) photoInput.value.value = ''
  await loadPeople()
}

async function addPhoto(personId: number, event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  rowError.value = ''
  busyId.value = personId
  const body = new FormData()
  body.append('photo', file)
  const response = await fetch(`/api/people/${personId}/photos`, {
    method: 'POST',
    credentials: 'include',
    body,
  })
  busyId.value = null
  if (!response.ok) {
    rowError.value = await errorMessage(response)
    return
  }
  await loadPeople()
}

async function removePerson(person: Person) {
  if (!window.confirm(`Delete ${person.name}?`)) return
  rowError.value = ''
  busyId.value = person.id
  const response = await fetch(`/api/people/${person.id}`, {
    method: 'DELETE',
    credentials: 'include',
  })
  busyId.value = null
  if (!response.ok) {
    rowError.value = await errorMessage(response)
    return
  }
  await loadPeople()
}

onMounted(loadPeople)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div class="space-y-1">
        <h1 class="page-title">People</h1>
        <p class="muted">Faces the camera can recognize.</p>
      </div>
      <span v-if="!loading" class="chip">{{ people.length }} enrolled</span>
    </div>

    <form class="card card-pad space-y-4" @submit.prevent="createPerson">
      <h2 class="text-sm font-medium">Add a person</h2>
      <div class="grid gap-5 sm:grid-cols-2">
        <label class="block">
          <span class="field-label">Name</span>
          <input v-model="name" class="field" autocomplete="off" placeholder="Full name" />
        </label>
        <label class="block">
          <span class="field-label">Photo</span>
          <input ref="photoInput" class="file" type="file" accept="image/*" @change="onPhotoChange" />
        </label>
      </div>
      <p class="muted">Use one clear photo with a single face.</p>
      <p v-if="formError" class="error">{{ formError }}</p>
      <button class="btn" type="submit" :disabled="saving">
        {{ saving ? 'Adding…' : 'Add person' }}
      </button>
    </form>

    <p v-if="loading" class="muted">Loading…</p>
    <p v-else-if="loadError" class="error">{{ loadError }}</p>
    <p v-if="rowError" class="error">{{ rowError }}</p>

    <div v-if="!loading && people.length === 0" class="card card-pad">
      <p class="muted">No people enrolled yet. Add someone above to start recognizing faces.</p>
    </div>

    <ul v-else-if="!loading" class="card divide-y divide-line">
      <li v-for="person in people" :key="person.id" class="flex flex-wrap items-center gap-6 px-6 py-5">
        <div class="min-w-36">
          <p class="font-medium">{{ person.name }}</p>
          <p class="muted mt-1">{{ person.sample_count }} photo{{ person.sample_count === 1 ? '' : 's' }}</p>
        </div>
        <label class="muted ml-auto flex items-center gap-3">
          Add photo
          <input
            class="text-sm"
            type="file"
            accept="image/*"
            :disabled="busyId === person.id"
            :aria-label="`Add photo for ${person.name}`"
            @change="addPhoto(person.id, $event)"
          />
        </label>
        <button class="btn-danger" type="button" :disabled="busyId === person.id" @click="removePerson(person)">
          Delete
        </button>
      </li>
    </ul>
  </section>
</template>
