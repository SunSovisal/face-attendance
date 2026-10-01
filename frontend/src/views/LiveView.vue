<script setup lang="ts">
import { nextTick, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'

type Face = {
  box: [number, number, number, number]
  person_id: number | null
  name: string
  distance: number
  matched: boolean
  match_token?: string
}

type Payload = {
  frame_width: number
  frame_height: number
  faces: Face[]
}

type Pending = {
  personId: number
  name: string
  distance: number
  token: string
}

const router = useRouter()
const videoRef = ref<HTMLVideoElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const running = ref(false)
const error = ref('')
const confirmError = ref('')
const notice = ref('')
const saving = ref(false)
const pending = ref<Pending | null>(null)
const loggedToday = ref<number[]>([])

let stream: MediaStream | null = null
let socket: WebSocket | null = null
let stopRequested = false
let streakId: number | null = null
let streakCount = 0
const ignoredUntil = new Map<number, number>()

function today() {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Phnom_Penh' }).format(new Date())
}

async function loadToday() {
  const day = today()
  const response = await fetch(`/api/attendance?from=${day}&to=${day}`, { credentials: 'include' })
  if (response.status === 401) {
    router.push('/login')
    return
  }
  if (!response.ok) return
  const rows = (await response.json()) as { person_id: number | null }[]
  loggedToday.value = rows.flatMap((row) => (typeof row.person_id === 'number' ? [row.person_id] : []))
}

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
    const label = face.matched ? `${face.name} ${face.distance.toFixed(2)}` : 'Unknown'
    context.fillText(label, x1, Math.max(16, y1 - 6))
  }
}

function boxArea(face: Face) {
  return (face.box[2] - face.box[0]) * (face.box[3] - face.box[1])
}

function refreshPending(faces: Face[]) {
  if (!pending.value) return
  const same = faces.find(
    (face) => face.matched && face.person_id === pending.value?.personId && face.match_token,
  )
  if (!same?.match_token || same.person_id == null) return
  pending.value = {
    personId: same.person_id,
    name: same.name,
    distance: same.distance,
    token: same.match_token,
  }
}

function noteFrame(faces: Face[]) {
  refreshPending(faces)
  if (pending.value) return
  const known = faces
    .filter((face) => face.matched && face.person_id != null && face.match_token)
    .sort((a, b) => boxArea(b) - boxArea(a))
  const best = known[0]
  if (!best || best.person_id == null || !best.match_token) {
    streakId = null
    streakCount = 0
    return
  }
  const now = Date.now()
  if (loggedToday.value.includes(best.person_id) || now < (ignoredUntil.get(best.person_id) ?? 0)) {
    streakId = null
    streakCount = 0
    return
  }
  if (streakId === best.person_id) streakCount += 1
  else {
    streakId = best.person_id
    streakCount = 1
  }
  if (streakCount < 3) return
  pending.value = {
    personId: best.person_id,
    name: best.name,
    distance: best.distance,
    token: best.match_token,
  }
  streakId = null
  streakCount = 0
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
    next.addEventListener(
      'close',
      () => reject(new Error('Recognition disconnected.')),
      { once: true },
    )
  })
}

async function start() {
  error.value = ''
  notice.value = ''
  confirmError.value = ''
  stopRequested = false
  await loadToday()
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

async function confirmYes() {
  if (!pending.value || saving.value) return
  saving.value = true
  confirmError.value = ''
  const current = pending.value
  const response = await fetch('/api/attendance', {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ match_token: current.token }),
  })
  saving.value = false
  if (response.status === 409 || response.ok) {
    if (!loggedToday.value.includes(current.personId)) {
      loggedToday.value = [...loggedToday.value, current.personId]
    }
    notice.value = response.status === 409 ? `${current.name} is already logged today` : `${current.name} logged for today`
    confirmError.value = ''
    pending.value = null
    return
  }
  confirmError.value = response.status === 400 ? 'That match expired. Keep the face in view and try again.' : 'Could not save attendance.'
}

function dismiss() {
  if (!pending.value) return
  ignoredUntil.set(pending.value.personId, Date.now() + 8000)
  pending.value = null
  confirmError.value = ''
}

onUnmounted(stop)
</script>

<template>
  <section class="space-y-6">
    <div class="flex flex-wrap items-end justify-between gap-4">
      <div class="space-y-1">
        <h1 class="page-title">Live</h1>
        <p class="muted">Recognize faces from your camera and confirm check-ins.</p>
      </div>
      <button v-if="running" class="btn-quiet" type="button" @click="stop">Stop camera</button>
    </div>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="notice" class="muted">{{ notice }}</p>

    <div class="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
      <div class="card relative overflow-hidden">
        <video ref="videoRef" class="pointer-events-none absolute h-px w-px opacity-0" playsinline muted />
        <canvas v-show="running" ref="canvasRef" class="block h-auto w-full" />
        <div v-if="!running" class="card-pad grid place-items-center gap-4 py-12 text-center">
          <p class="text-sm font-medium">Camera is not running</p>
          <p class="muted max-w-sm">
            Start the camera to see faces with a box and a name. A person is logged only after you confirm.
          </p>
          <button class="btn" type="button" @click="start">Start camera</button>
        </div>
      </div>

      <aside class="card card-pad space-y-4">
        <h2 class="text-sm font-medium">Confirm</h2>
        <template v-if="pending">
          <p class="text-lg font-semibold tracking-tight">{{ pending.name }}</p>
          <p class="muted">Distance {{ pending.distance.toFixed(2) }}</p>
          <p v-if="confirmError" class="error">{{ confirmError }}</p>
          <div class="flex flex-wrap gap-3">
            <button class="btn" type="button" :disabled="saving" @click="confirmYes">
              {{ saving ? 'Saving…' : 'Yes' }}
            </button>
            <button class="btn-quiet" type="button" :disabled="saving" @click="dismiss">Not this person</button>
          </div>
        </template>
        <p v-else class="muted">A known face must hold steady before you can log them.</p>
      </aside>
    </div>
  </section>
</template>
