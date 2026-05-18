<script setup lang="ts">
import { Check, Delete, Plus } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

import FieldHelpLabel from '@/components/common/FieldHelpLabel.vue'

const model = defineModel<string[]>({ required: true })
defineProps<{ label: string; help?: string; applying?: boolean }>()
const emit = defineEmits<{ apply: [] }>()
const { t } = useI18n()

function addCommand() {
  model.value = [...model.value, '']
}

function updateCommand(index: number, value: string) {
  model.value = model.value.map((item, itemIndex) => (itemIndex === index ? value : item))
}

function removeCommand(index: number) {
  model.value = model.value.filter((_, itemIndex) => itemIndex !== index)
  emit('apply')
}
</script>

<template>
  <section class="hook-editor">
    <div class="hook-editor__head">
      <strong>
        <FieldHelpLabel v-if="help" :label="label" :help="help" />
        <span v-else>{{ label }}</span>
      </strong>
      <el-button size="small" :icon="Plus" @click="addCommand">{{ t('nodeAdvanced.addCommand') }}</el-button>
    </div>
    <div v-if="model.length" class="hook-editor__list">
      <div v-for="(command, index) in model" :key="index" class="hook-editor__row">
        <el-input :model-value="command" @update:model-value="(value: string) => updateCommand(index, value)" />
        <div class="hook-editor__actions">
          <el-button :icon="Check" :loading="applying" :aria-label="t('node.apply')" @click="emit('apply')" />
          <el-button :icon="Delete" :aria-label="t('common.delete')" @click="removeCommand(index)" />
        </div>
      </div>
    </div>
    <div v-else class="hook-editor__empty">{{ t('nodeAdvanced.noCommands') }}</div>
  </section>
</template>

<style scoped>
.hook-editor { display: grid; gap: 10px; padding: 12px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-elevated); }
.hook-editor__head,
.hook-editor__row { display: flex; align-items: center; gap: 10px; }
.hook-editor__head { justify-content: space-between; }
.hook-editor__head strong { color: var(--app-text); }
.hook-editor__list { display: grid; gap: 8px; }
.hook-editor__row .el-input { min-width: 0; }
.hook-editor__actions { display: inline-flex; align-items: center; gap: 6px; }
.hook-editor__empty { color: var(--app-faint); font-size: 13px; }
@media (max-width: 720px) {
  .hook-editor__head,
  .hook-editor__row { align-items: stretch; flex-direction: column; }
  .hook-editor__actions { justify-content: flex-end; }
}
</style>
