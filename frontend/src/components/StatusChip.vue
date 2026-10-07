<script setup lang="ts">
import { computed } from 'vue'
import { capitalize, statusClass, statusLabel } from '../format'

const props = defineProps<{ status: string; label?: string }>()
const text = computed(() => {
  if (props.label) return props.label
  const known = statusLabel(props.status)
  return known === props.status ? capitalize(props.status) : known
})
</script>

<template>
  <span :class="statusClass(status)">{{ text }}</span>
</template>
