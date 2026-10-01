<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from './stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const showNav = computed(() => route.path !== '/login')

async function logout() {
  await auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="min-h-screen">
    <header v-if="showNav" class="border-b border-line bg-panel">
      <div class="shell flex items-center gap-6 py-3">
        <span class="text-sm font-semibold tracking-tight">Attendance</span>
        <nav class="flex items-center gap-1">
          <RouterLink class="nav-link" to="/live">Live</RouterLink>
          <RouterLink class="nav-link" to="/people">People</RouterLink>
          <RouterLink class="nav-link" to="/attendance">Attendance</RouterLink>
        </nav>
        <button class="btn-quiet ml-auto" type="button" @click="logout">Log out</button>
      </div>
    </header>
    <main :class="showNav ? 'page-shell' : 'login-shell'">
      <RouterView />
    </main>
  </div>
</template>
