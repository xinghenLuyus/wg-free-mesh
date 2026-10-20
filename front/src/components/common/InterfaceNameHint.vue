<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ configName: string; nodeName?: string }>()
const { t } = useI18n()

// Display-only length estimate for the existing exported filename encoding.
function nameSegment(value: string) {
  return Array.from(value.trim(), (char) => /^[a-zA-Z0-9_.-]$/.test(char)
    ? char
    : `u${char.codePointAt(0)!.toString(16).padStart(4, '0')}`,
  ).join('').replace(/^[-_.]+|[-_.]+$/g, '')
}

const message = computed(() => {
  const config = nameSegment(props.configName)
  if (props.nodeName === undefined) {
    return config.length > 12 ? t('naming.configNameWarning') : ''
  }
  const node = nameSegment(props.nodeName)
  const name = `${config || 'wireguard'}-${node || 'node'}`
  return props.configName.trim() && props.nodeName.trim() && name.length > 15
    ? t('naming.interfaceNameWarning', { name, length: name.length })
    : ''
})
</script>

<template>
  <p v-if="message" class="interface-name-hint" role="status">{{ message }}</p>
</template>

<style scoped>
.interface-name-hint { width: 100%; margin: 6px 0 0; color: var(--el-color-warning); font-size: 12px; line-height: 1.5; overflow-wrap: anywhere; }
</style>
