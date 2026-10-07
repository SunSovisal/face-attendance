<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'

const props = defineProps<{
  modelValue: string
  options: { value: string; label: string }[]
  ariaLabel?: string
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  change: []
}>()

const open = ref(false)
const root = ref<HTMLElement | null>(null)
const active = ref(0)

const current = computed(() => props.options.find((option) => option.value === props.modelValue)?.label ?? '')

function toggle() {
  open.value = !open.value
  if (!open.value) return
  const index = props.options.findIndex((option) => option.value === props.modelValue)
  active.value = index >= 0 ? index : 0
}

function choose(value: string) {
  open.value = false
  if (value === props.modelValue) return
  emit('update:modelValue', value)
  emit('change')
}

function onPointerDown(event: PointerEvent) {
  if (!root.value?.contains(event.target as Node)) open.value = false
}

function onKey(event: KeyboardEvent) {
  if (!open.value && (event.key === 'ArrowDown' || event.key === 'Enter' || event.key === ' ')) {
    event.preventDefault()
    toggle()
    return
  }
  if (!open.value) return
  if (event.key === 'Escape') {
    event.preventDefault()
    open.value = false
    return
  }
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    active.value = Math.min(props.options.length - 1, active.value + 1)
    return
  }
  if (event.key === 'ArrowUp') {
    event.preventDefault()
    active.value = Math.max(0, active.value - 1)
    return
  }
  if (event.key === 'Enter') {
    event.preventDefault()
    const option = props.options[active.value]
    if (option) choose(option.value)
  }
}

document.addEventListener('pointerdown', onPointerDown)
onUnmounted(() => document.removeEventListener('pointerdown', onPointerDown))
</script>

<template>
  <div ref="root" class="relative">
    <button
      class="field field-select"
      type="button"
      :aria-label="ariaLabel"
      aria-haspopup="listbox"
      :aria-expanded="open"
      @click="toggle"
      @keydown="onKey"
    >
      <span class="truncate">{{ current }}</span>
    </button>
    <ul v-if="open" class="menu-list" role="listbox">
      <li v-for="(option, index) in options" :key="`${option.value}-${option.label}`">
        <button
          class="menu-option"
          :class="{ 'menu-option-active': index === active, 'menu-option-selected': option.value === modelValue }"
          type="button"
          role="option"
          :aria-selected="option.value === modelValue"
          @mouseenter="active = index"
          @click="choose(option.value)"
        >
          <span class="truncate">{{ option.label }}</span>
          <span v-if="option.value === modelValue" class="menu-check" aria-hidden="true">✓</span>
        </button>
      </li>
    </ul>
  </div>
</template>
