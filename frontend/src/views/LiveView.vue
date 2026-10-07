<script setup lang="ts">
import { nextTick, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, errorText, unauthorized } from '../api'
import PageHeader from '../components/PageHeader.vue'
import UserAvatar from '../components/UserAvatar.vue'
import { formatTime } from '../format'

type Face = {
  box: [number, number, number, number]
  employee_id: number | null
  name: string
  distance: number
  matched: boolean
  spoof?: boolean
  action?: 'check_in' | 'check_out' | 'done'
  match_token?: string
  confidence?: 'sure' | 'close' | null
  held?: boolean
  employee_code?: string
  position?: string
  department?: string
}

type Payload = {
  frame_width: number
  frame_height: number
  faces: Face[]
}

type Pending = {
  employeeId: number
  name: string
  distance: number
  token: string
  action: 'check_in' | 'check_out'
  mode: 'auto' | 'ask'
  department: string
  position: string
  employeeCode: string
}

type PunchResult = {
  action?: string
  undo_token?: string
  undo_seconds?: number
  check_in_at?: string | null
  check_out_at?: string | null
}

type Undo = {
  token: string
  name: string
  action: 'check_in' | 'check_out'
  at: string
  recentId: number
}

const router = useRouter()
const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const running = ref(false)
const error = ref('')
const confirmError = ref('')
const notice = ref('')
const saving = ref(false)
const undoing = ref(false)
const pending = ref<Pending | null>(null)
const undo = ref<Undo | null>(null)
const settling = ref('')
const photoMissing = ref(false)
const photoInFrame = ref(false)
const recent = ref<{ id: number; name: string; action: 'check_in' | 'check_out'; at: string }[]>([])
let recentId = 0
let undoTimer = 0

let stream: MediaStream | null = null
let socket: WebSocket | null = null
let stopRequested = false
let streakId: number | null = null
let streakCount = 0
const ignoredUntil = new Map<number, number>()

function fitSize(width: number, height: number) {
  const scale = Math.min(1, 640 / Math.max(width, height))
  return {
    width: Math.max(1, Math.round(width * scale)),
    height: Math.max(1, Math.round(height * scale)),
  }
}

function drawVideo(video: HTMLVideoElement, canvas: HTMLCanvasElement) {
  const size = fitSize(video.videoWidth, video.videoHeight)
  if (canvas.width !== size.width) canvas.width = size.width
  if (canvas.height !== size.height) canvas.height = size.height
  const context = canvas.getContext('2d')
  if (!context) return
  context.drawImage(video, 0, 0, size.width, size.height)
}

function drawFaces(canvas: HTMLCanvasElement, faces: Face[]) {
  const context = canvas.getContext('2d')
  if (!context) return
  const styles = getComputedStyle(document.documentElement)
  const good = styles.getPropertyValue('--color-good').trim() || '#1d7a4f'
  const danger = styles.getPropertyValue('--color-danger').trim() || '#b3261e'
  context.lineWidth = 2
  context.font = '600 14px Inter, ui-sans-serif, system-ui, sans-serif'
  for (const face of faces) {
    const [x1, y1, x2, y2] = face.box
    const color = face.matched ? good : danger
    context.strokeStyle = color
    context.fillStyle = color
    context.strokeRect(x1, y1, x2 - x1, y2 - y1)
    const label = face.spoof ? 'Photo' : face.matched ? `${face.name} ${face.distance.toFixed(2)}` : 'Unknown'
    context.fillText(label, x1, Math.max(16, y1 - 6))
  }
}

function boxArea(face: Face) {
  return (face.box[2] - face.box[0]) * (face.box[3] - face.box[1])
}

function asPending(face: Face): Pending | null {
  if (face.employee_id == null || !face.match_token) return null
  return {
    employeeId: face.employee_id,
    name: face.name,
    distance: face.distance,
    token: face.match_token,
    action: face.action === 'check_out' ? 'check_out' : 'check_in',
    mode: face.confidence === 'sure' ? 'auto' : 'ask',
    department: face.department ?? '',
    position: face.position ?? '',
    employeeCode: face.employee_code ?? '',
  }
}

function showPending(next: Pending) {
  if (pending.value?.employeeId !== next.employeeId) photoMissing.value = false
  const mode = pending.value?.employeeId === next.employeeId ? pending.value.mode : next.mode
  pending.value = { ...next, mode }
}

function armUndo(next: Undo, seconds: number) {
  undo.value = next
  window.clearTimeout(undoTimer)
  undoTimer = window.setTimeout(() => {
    undo.value = null
  }, Math.max(1, seconds) * 1000)
}

function refreshPending(faces: Face[]) {
  if (!pending.value) return
  const same = faces.find((face) => face.employee_id === pending.value?.employeeId)
  if (!same || same.action === 'done' || !same.match_token || same.employee_id == null) {
    if (same?.action === 'done') pending.value = null
    return
  }
  const next = asPending(same)
  if (next) showPending(next)
}

function noteFrame(faces: Face[]) {
  photoInFrame.value = faces.some((face) => face.spoof)
  if (saving.value) return
  refreshPending(faces)
  if (pending.value) return
  const known = faces
    .filter((face) => face.matched && face.employee_id != null && face.match_token && face.action !== 'done')
    .sort((a, b) => boxArea(b) - boxArea(a))
  const best = known[0]
  if (!best || best.employee_id == null || !best.match_token) {
    streakId = null
    streakCount = 0
    settling.value = ''
    return
  }
  const now = Date.now()
  if (now < (ignoredUntil.get(best.employee_id) ?? 0)) {
    streakId = null
    streakCount = 0
    settling.value = ''
    return
  }
  if (streakId === best.employee_id) streakCount += 1
  else {
    streakId = best.employee_id
    streakCount = 1
  }
  if (streakCount < 3) {
    settling.value = best.name
    return
  }
  const next = asPending(best)
  settling.value = ''
  if (!next) return
  showPending(next)
  streakId = null
  streakCount = 0
  if (next.mode === 'auto') void confirmYes()
}

function sleep(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

function canvasBlob(canvas: HTMLCanvasElement) {
  return new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.7))
}

function sendFrame(buffer: ArrayBuffer) {
  return new Promise<Payload | null>((resolve) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      resolve(null)
      return
    }
    const onMessage = (event: MessageEvent) => {
      cleanup()
      try {
        resolve(JSON.parse(String(event.data)) as Payload)
      } catch {
        resolve(null)
      }
    }
    const onClose = () => {
      cleanup()
      resolve(null)
    }
    const cleanup = () => {
      socket?.removeEventListener('message', onMessage)
      socket?.removeEventListener('close', onClose)
    }
    socket.addEventListener('message', onMessage)
    socket.addEventListener('close', onClose)
    socket.send(buffer)
  })
}

async function recognizeLoop() {
  while (!stopRequested && socket?.readyState === WebSocket.OPEN) {
    const video = videoRef.value
    const canvas = canvasRef.value
    if (!video || !canvas || video.videoWidth === 0) {
      await sleep(100)
      continue
    }
    const started = Date.now()
    drawVideo(video, canvas)
    const blob = await canvasBlob(canvas)
    if (!blob || stopRequested) return
    const payload = await sendFrame(await blob.arrayBuffer())
    if (!payload || stopRequested) return
    drawFaces(canvas, payload.faces)
    noteFrame(payload.faces)
    const remaining = 300 - (Date.now() - started)
    if (remaining > 0) await sleep(remaining)
  }
}

function openSocket() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const next = new WebSocket(`${protocol}://${location.host}/api/recognize`)
  socket = next
  return new Promise<void>((resolve, reject) => {
    next.addEventListener('open', () => resolve(), { once: true })
    next.addEventListener('close', () => reject(new Error('Recognition disconnected.')), { once: true })
  })
}

async function start() {
  error.value = ''
  notice.value = ''
  confirmError.value = ''
  stopRequested = false
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'user' },
      audio: false,
    })
  } catch {
    error.value = 'The camera could not be opened.'
    return
  }
  running.value = true
  await nextTick()
  const video = videoRef.value
  if (!video) return
  video.srcObject = stream
  try {
    await video.play()
    await openSocket()
  } catch {
    error.value = 'Recognition could not start. Sign in again if this keeps happening.'
    stop()
    return
  }
  void recognizeLoop()
}

function stop() {
  stopRequested = true
  socket?.close()
  socket = null
  stream?.getTracks().forEach((track) => track.stop())
  stream = null
  if (videoRef.value) videoRef.value.srcObject = null
  running.value = false
  pending.value = null
  streakId = null
  streakCount = 0
}

async function snapshotBlob() {
  const video = videoRef.value
  if (!video || video.videoWidth === 0) return null
  const canvas = document.createElement('canvas')
  const size = fitSize(video.videoWidth, video.videoHeight)
  canvas.width = size.width
  canvas.height = size.height
  const context = canvas.getContext('2d')
  if (!context) return null
  context.drawImage(video, 0, 0, size.width, size.height)
  return canvasBlob(canvas)
}

async function confirmYes() {
  if (!pending.value || saving.value) return
  saving.value = true
  confirmError.value = ''
  const current = pending.value
  const shot = await snapshotBlob()
  if (!shot) {
    confirmError.value = 'Could not capture the current frame.'
    saving.value = false
    if (current.mode === 'auto') {
      ignoredUntil.set(current.employeeId, Date.now() + 8000)
      pending.value = null
    }
    return
  }
  const body = new FormData()
  body.append('match_token', current.token)
  body.append('snapshot', shot, 'check-in.jpg')
  try {
    const saved = await api<PunchResult>(`/api/attendance/punch`, { method: 'POST', body })
    const action: Pending['action'] = saved.action === 'check_out' ? 'check_out' : 'check_in'
    const at = formatTime((action === 'check_out' ? saved.check_out_at : saved.check_in_at) || new Date().toISOString())
    const id = ++recentId
    recent.value = [{ id, name: current.name, action, at }, ...recent.value].slice(0, 8)
    if (saved.undo_token) {
      notice.value = ''
      armUndo({ token: saved.undo_token, name: current.name, action, at, recentId: id }, saved.undo_seconds ?? 8)
    } else {
      notice.value = `${current.name} ${action === 'check_out' ? 'checked out' : 'checked in'}.`
    }
    pending.value = null
  } catch (err) {
    if (unauthorized(err)) {
      router.push('/login')
      return
    }
    confirmError.value = errorText(err)
    if (current.mode === 'auto') {
      ignoredUntil.set(current.employeeId, Date.now() + 8000)
      pending.value = null
    }
  } finally {
    saving.value = false
  }
}

async function undoPunch() {
  if (!undo.value || undoing.value) return
  undoing.value = true
  confirmError.value = ''
  const current = undo.value
  try {
    await api('/api/attendance/undo', {
      method: 'POST',
      body: JSON.stringify({ undo_token: current.token }),
    })
    window.clearTimeout(undoTimer)
    undo.value = null
    notice.value = `Undone. ${current.name} was not ${current.action === 'check_out' ? 'checked out' : 'checked in'}.`
    recent.value = recent.value.filter((entry) => entry.id !== current.recentId)
  } catch (err) {
    if (unauthorized(err)) {
      router.push('/login')
      return
    }
    confirmError.value = errorText(err)
  } finally {
    undoing.value = false
  }
}

function dismiss() {
  if (!pending.value) return
  ignoredUntil.set(pending.value.employeeId, Date.now() + 8000)
  pending.value = null
  confirmError.value = ''
}

onUnmounted(() => {
  window.clearTimeout(undoTimer)
  stop()
})
</script>

<template>
  <section class="space-y-6">
    <PageHeader title="Live desk" subtitle="A clear match is saved on its own. A close match waits for you.">
      <span v-if="running" class="chip chip-good">
        <span class="h-1.5 w-1.5 rounded-full bg-good" aria-hidden="true"></span>
        Camera on
      </span>
      <button v-if="running" class="btn-quiet" type="button" @click="stop">Stop camera</button>
    </PageHeader>

    <p v-if="error" class="notice notice-danger" role="alert">{{ error }}</p>
    <p v-else-if="undo" class="notice notice-good" role="status">
      {{ undo.name }} {{ undo.action === 'check_out' ? 'checked out' : 'checked in' }} at {{ undo.at }}.
      <button class="btn-link !px-1" type="button" :disabled="undoing" @click="undoPunch">
        {{ undoing ? 'Undoing…' : 'Undo' }}
      </button>
    </p>
    <p v-else-if="notice" class="notice notice-good" role="status">{{ notice }}</p>
    <p v-if="confirmError" class="notice notice-danger" role="alert">{{ confirmError }}</p>

    <div class="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_22rem]">
      <div class="card relative overflow-hidden">
        <video ref="videoRef" class="pointer-events-none absolute h-px w-px opacity-0" playsinline muted />
        <canvas v-show="running" ref="canvasRef" class="block h-auto w-full" />
        <div v-if="!running" class="empty aspect-[4/3] max-h-[28rem] w-full gap-3">
          <span class="avatar avatar-lg text-lg" aria-hidden="true">◎</span>
          <p class="section-title">Camera is off</p>
          <p class="muted max-w-sm">A clear match checks in on its own. You still confirm a close one.</p>
          <button class="btn mt-2" type="button" @click="start">Start camera</button>
        </div>
      </div>

      <aside class="space-y-4">
        <div class="card overflow-hidden" aria-live="polite">
          <template v-if="pending">
            <img
              v-if="!photoMissing"
              :src="`/api/employees/${pending.employeeId}/photo`"
              :alt="`${pending.name}'s enrolled photo`"
              class="aspect-[3/4] w-full bg-soft object-cover object-top"
              @error="photoMissing = true"
            />
            <div v-else class="grid aspect-[3/4] w-full place-items-center bg-soft">
              <UserAvatar :name="pending.name" large />
            </div>
            <div class="space-y-4 p-5">
              <div class="min-w-0">
                <p class="truncate text-xl font-semibold tracking-tight">{{ pending.name }}</p>
                <p class="muted">{{ pending.department || 'No department' }}</p>
              </div>
              <dl class="grid grid-cols-[5.5rem_minmax(0,1fr)] gap-y-1.5 text-sm">
                <dt class="text-mute">Code</dt>
                <dd class="truncate">{{ pending.employeeCode || '—' }}</dd>
                <dt class="text-mute">Position</dt>
                <dd class="truncate">{{ pending.position || '—' }}</dd>
                <dt class="text-mute">Match</dt>
                <dd class="num">{{ pending.distance.toFixed(2) }}</dd>
              </dl>
              <p v-if="pending.mode === 'auto'" class="text-sm">Saving this punch.</p>
              <p v-else class="text-sm">Close match. Confirm this is them.</p>
              <div v-if="pending.mode !== 'auto'" class="grid gap-2">
                <button class="btn btn-block !py-3 !text-base" type="button" :disabled="saving" @click="confirmYes">
                  {{ saving ? 'Saving…' : pending.action === 'check_out' ? 'Check out' : 'Check in' }}
                </button>
                <button class="btn-quiet btn-block" type="button" :disabled="saving" @click="dismiss">Not this person</button>
              </div>
            </div>
          </template>
          <p v-else-if="running && photoInFrame" class="muted p-5">
            That looks like a photo. Hold a live face in view.
          </p>
          <p v-else-if="running && settling" class="muted p-5">Hold still, {{ settling }}…</p>
          <p v-else class="muted p-5">
            {{ running ? 'Waiting for a known face to hold steady…' : 'Start the camera to begin.' }}
          </p>
        </div>

        <div class="card">
          <div class="card-head !py-3">
            <p class="section-title">This session</p>
            <span class="muted">{{ recent.length }}</span>
          </div>
          <ul v-if="recent.length" class="list">
            <li v-for="entry in recent" :key="entry.id" class="flex items-center gap-3 px-5 py-2.5 text-sm">
              <span class="min-w-0 flex-1 truncate">{{ entry.name }}</span>
              <span :class="entry.action === 'check_out' ? 'chip chip-neutral' : 'chip chip-good'">
                {{ entry.action === 'check_out' ? 'Out' : 'In' }}
              </span>
              <span class="num text-mute">{{ entry.at }}</span>
            </li>
          </ul>
          <p v-else class="muted px-5 py-4">No punches yet.</p>
        </div>
      </aside>
    </div>
  </section>
</template>

