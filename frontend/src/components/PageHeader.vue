<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>()
</script>

<template>
  <div class="page-head">
    <div class="min-w-0 space-y-1">
      <h1 class="page-title">{{ title }}</h1>
      <p v-if="subtitle" class="muted">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.default" class="page-actions">
      <slot />
    </div>
  </div>
</template>
