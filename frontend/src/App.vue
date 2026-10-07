<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from './api'
import UserAvatar from './components/UserAvatar.vue'
import { roleLabel } from './format'
import { useAuthStore } from './stores/auth'

type Item = { to: string; label: string; badge?: number }
type Group = { label: string; items: Item[] }

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const open = ref(false)
const pendingLeave = ref(0)
const pendingAccounts = ref(0)
const pendingFixes = ref(0)
const wideQuery = window.matchMedia('(min-width: 1024px)')
const wide = ref(wideQuery.matches)

function onWide(event: MediaQueryListEvent) {
  wide.value = event.matches
  if (event.matches) open.value = false
}

wideQuery.addEventListener('change', onWide)

const isPublic = computed(() => route.path === '/login' || route.path === '/register')
const isStaff = computed(() => auth.me?.status === 'active' && auth.me.role !== 'employee')
const displayName = computed(() => auth.me?.employee_name || auth.me?.username || '')

const groups = computed<Group[]>(() => {
  const me = auth.me
  if (!me || me.status !== 'active') return []
  if (me.role === 'employee') {
    return [
      {
        label: 'My record',
        items: [
          { to: '/me', label: 'My attendance' },
          { to: '/leave', label: 'Leave' },
        ],
      },
    ]
  }
  const sections: Group[] = [
    {
      label: 'Desk',
      items: [
        { to: '/live', label: 'Live desk' },
        { to: '/today', label: 'Today' },
      ],
    },
    {
      label: 'Records',
      items: [
        { to: '/attendance', label: 'Attendance', badge: pendingFixes.value },
        { to: '/month', label: 'Month summary' },
      ],
    },
    {
      label: 'People',
      items: [
        { to: '/employees', label: 'Employees', badge: pendingAccounts.value },
        { to: '/leave', label: 'Leave', badge: pendingLeave.value },
        { to: '/holidays', label: 'Holidays' },
      ],
    },
  ]
  if (me.role === 'super_admin') {
    sections.push({
      label: 'Office',
      items: [
        { to: '/accounts', label: 'Accounts' },
        { to: '/office', label: 'Office hours' },
      ],
    })
  }
  return sections
})

const hasNav = computed(() => !isPublic.value && groups.value.length > 0)

const pageTitle = computed(() => {
  if (route.path === '/password') return 'Password'
  for (const group of groups.value) {
    const item = group.items.find((entry) => route.path === entry.to)
    if (item) return item.label
  }
  return 'Attendance'
})

async function refreshBadges() {
  if (!isStaff.value) return
  try {
    const [leave, roster, fixes] = await Promise.all([
      api<{ status: string }[]>('/api/leave'),
      api<{ account_status: string | null }[]>('/api/employees'),
      api<{ status: string }[]>('/api/corrections?status=pending'),
    ])
    pendingLeave.value = leave.filter((row) => row.status === 'pending').length
    pendingAccounts.value = roster.filter((row) => row.account_status === 'pending').length
    pendingFixes.value = fixes.length
  } catch {
    pendingLeave.value = 0
    pendingAccounts.value = 0
    pendingFixes.value = 0
  }
}

function closeMenu() {
  open.value = false
}

function onKey(event: KeyboardEvent) {
  if (event.key === 'Escape') closeMenu()
}

watch(
  () => route.fullPath,
  () => {
    closeMenu()
    void refreshBadges()
  },
)

function onBadges() {
  void refreshBadges()
}

window.addEventListener('badges-refresh', onBadges)

watch(
  () => auth.me?.id,
  () => void refreshBadges(),
  { immediate: true },
)

watch(open, (value) => {
  document.body.style.overflow = value ? 'hidden' : ''
  if (value) window.addEventListener('keydown', onKey)
  else window.removeEventListener('keydown', onKey)
})

onUnmounted(() => {
  document.body.style.overflow = ''
  window.removeEventListener('keydown', onKey)
  window.removeEventListener('badges-refresh', onBadges)
  wideQuery.removeEventListener('change', onWide)
})

async function logout() {
  closeMenu()
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <main v-if="isPublic" class="login-shell">
    <RouterView />
  </main>

  <div v-else class="app-frame" :class="{ 'has-nav': hasNav }">
    <div v-if="open" class="menu-backdrop" @click="closeMenu"></div>

    <aside v-if="hasNav" id="side-menu" class="sidebar" :class="{ 'sidebar-open': open }" :inert="!wide && !open">
      <div class="sidebar-head">
        <span class="brand-mark" aria-hidden="true">A</span>
        <RouterLink class="text-sm font-semibold tracking-tight" to="/">Attendance</RouterLink>
        <button class="menu-button sidebar-close ml-auto" type="button" aria-label="Close menu" @click="closeMenu">
          <span aria-hidden="true" class="text-lg leading-none">×</span>
        </button>
      </div>

      <nav class="sidebar-nav" aria-label="Pages">
        <section v-for="group in groups" :key="group.label">
          <p class="menu-label">{{ group.label }}</p>
          <RouterLink v-for="item in group.items" :key="item.to" class="nav-link" :to="item.to">
            <span>{{ item.label }}</span>
            <span v-if="item.badge" class="nav-count" :aria-label="`${item.badge} waiting`">{{ item.badge }}</span>
          </RouterLink>
        </section>
      </nav>

      <div v-if="auth.me" class="sidebar-foot">
        <div class="flex items-center gap-3 px-1 pb-3">
          <UserAvatar :name="displayName" />
          <div class="min-w-0">
            <p class="truncate text-sm font-medium">{{ displayName }}</p>
            <p class="truncate text-xs text-mute">{{ roleLabel(auth.me.role) }} · {{ auth.me.username }}</p>
          </div>
        </div>
        <RouterLink class="btn-quiet btn-block mb-2 no-underline" to="/password">Password</RouterLink>
        <button class="btn-quiet btn-block" type="button" @click="logout">Log out</button>
      </div>
    </aside>

    <div class="app-main">
      <header class="topbar">
        <button
          v-if="hasNav"
          class="menu-button"
          type="button"
          :aria-expanded="open"
          aria-controls="side-menu"
          @click="open = true"
        >
          <span class="sr-only">Open menu</span>
          <span class="menu-mark" aria-hidden="true"></span>
        </button>
        <span v-else class="brand-mark" aria-hidden="true">A</span>
        <p class="truncate text-sm font-semibold tracking-tight">{{ pageTitle }}</p>
        <button v-if="!hasNav" class="btn-quiet btn-sm ml-auto" type="button" @click="logout">Log out</button>
      </header>

      <main class="page-shell">
        <RouterView />
      </main>
    </div>
  </div>
</template>
