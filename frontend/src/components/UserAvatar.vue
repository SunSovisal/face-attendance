<script setup lang="ts">
import { initials } from '../format'

defineProps<{ name: string; src?: string | null; large?: boolean }>()
</script>

<template>
  <img v-if="src" :src="src" alt="" class="avatar" :class="{ 'avatar-lg': large }" loading="lazy" />
  <span v-else class="avatar" :class="{ 'avatar-lg': large }" aria-hidden="true">{{ initials(name) }}</span>
</template>
