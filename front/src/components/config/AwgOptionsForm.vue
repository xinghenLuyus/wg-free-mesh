<script setup lang="ts">
import type { AwgOptions } from '@/types/api'
import { useI18n } from 'vue-i18n'
import FieldHelpLabel from '@/components/common/FieldHelpLabel.vue'

defineProps<{ fields: Record<string, string>; disabled?: boolean; help?: Record<string, string> }>()
const model = defineModel<AwgOptions>({ required: true })
const { t } = useI18n()

function setText(key: string, value: string) {
  model.value = { ...model.value, [key]: value.trim() || null }
}
</script>

<template>
  <div class="awg-options">
    <el-form-item v-for="(label, key) in fields" :key="key" :label="label">
      <template v-if="help?.[key]" #label>
        <FieldHelpLabel :label="label" :help="help?.[key] ?? ''" />
      </template>
      <el-select v-if="key === 'random_trailers' || key === 'disable_cookies'"
        :disabled="disabled"
        :model-value="model[key] ?? ''" @update:model-value="model = { ...model, [key]: $event === '' ? null : $event }">
        <el-option :value="''" :label="t('protocol.optionUnset')" />
        <el-option :value="true" label="on" />
        <el-option :value="false" label="off" />
      </el-select>
      <el-input v-else :model-value="String(model[key] ?? '')"
        :disabled="disabled"
        :show-password="key === 'header_protection_key'"
        @update:model-value="setText(String(key), $event)" />
    </el-form-item>
  </div>
</template>

<style scoped>
.awg-options { display: grid; gap: 8px; min-width: 0; }
</style>
