<script setup lang="ts">
import { computed } from 'vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const disabled = computed(() => auth.me?.status === 'disabled')
</script>

<template>
  <section class="mx-auto mt-8 max-w-md">
    <div class="card card-pad space-y-4 text-center">
      <span class="chip mx-auto" :class="disabled ? 'chip-danger' : 'chip-warn'">
        {{ disabled ? 'Account disabled' : 'Awaiting approval' }}
      </span>
      <h1 class="page-title">{{ disabled ? 'This account is turned off' : 'You are almost in' }}</h1>
      <p v-if="disabled" class="muted">Ask the office administrator to re-enable your login.</p>
      <template v-else>
        <p class="muted">An admin needs to approve your account. They will also add a face photo so the camera can recognize you.</p>
        <ol class="space-y-2 rounded-xl bg-soft p-4 text-left text-sm">
          <li class="grid grid-cols-[3.5rem_1fr] items-center gap-3"><span class="chip chip-good justify-self-start">Done</span> Account created</li>
          <li class="grid grid-cols-[3.5rem_1fr] items-center gap-3"><span class="chip chip-warn justify-self-start">Next</span> Admin approves and adds your photo</li>
          <li class="grid grid-cols-[3.5rem_1fr] items-center gap-3"><span class="chip justify-self-start">Then</span> Check in at the front desk camera</li>
        </ol>
        <p class="muted">You can sign out and come back later.</p>
        <RouterLink class="btn-quiet" to="/password">Change password</RouterLink>
      </template>
    </div>
  </section>
</template>
