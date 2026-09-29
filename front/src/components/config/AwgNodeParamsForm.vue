<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import type { AwgNodeParams } from '@/types/api'
import AwgOptionsForm from './AwgOptionsForm.vue'

defineProps<{ fields: Record<string, string>; disabled?: boolean }>()
const model = defineModel<AwgNodeParams>({ required: true })
const { t } = useI18n()
const jFields = ['awg_jc', 'awg_jmin', 'awg_jmax'] as const
const jLabels = ['Jc', 'Jmin', 'Jmax'] as const
const iFields = ['awg_i1', 'awg_i2', 'awg_i3', 'awg_i4', 'awg_i5'] as const
</script>

<template>
  <div>
    <el-form-item v-for="(field, index) in jFields" :key="field" :label="jLabels[index]">
      <el-input-number v-model="model[field]" :min="0" :max="65535" :disabled="disabled" />
    </el-form-item>
    <el-form-item v-for="field in iFields" :key="field" :label="field.slice(4).toUpperCase()">
      <el-input v-model="model[field]" :disabled="disabled" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" :placeholder="t('protocol.cpsPlaceholder')" />
    </el-form-item>
    <AwgOptionsForm v-model="model.awg_options" :fields="fields" :disabled="disabled" />
  </div>
</template>
