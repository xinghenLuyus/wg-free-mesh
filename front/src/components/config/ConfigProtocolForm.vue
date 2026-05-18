<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { api } from '@/api/modules'

export interface ConfigProtocolModel {
  tunnel_protocol: 'wireguard' | 'amneziawg_2'
  awg_s1: number | null
  awg_s2: number | null
  awg_s3: number | null
  awg_s4: number | null
  awg_h1: string | null
  awg_h2: string | null
  awg_h3: string | null
  awg_h4: string | null
}

const model = defineModel<ConfigProtocolModel>({ required: true })
const { t } = useI18n()

const protocolOptions = computed(() => [
  { label: 'WireGuard', value: 'wireguard' },
  { label: 'AmneziaWG 2.0', value: 'amneziawg_2' },
])

const sFields = ['awg_s1', 'awg_s2', 'awg_s3', 'awg_s4'] as const
const hFields = ['awg_h1', 'awg_h2', 'awg_h3', 'awg_h4'] as const

async function randomizeAll() {
  const values = await api.randomAwgConfig()
  Object.assign(model.value, values)
}

async function randomizeOne(key: keyof ConfigProtocolModel) {
  const values = await api.randomAwgConfig()
  model.value[key] = values[key] as never
}
</script>

<template>
  <div class="protocol-form">
    <el-form-item :label="t('protocol.protocol')">
      <el-segmented v-model="model.tunnel_protocol" :options="protocolOptions" />
    </el-form-item>

    <section v-if="model.tunnel_protocol === 'amneziawg_2'" class="protocol-form__awg">
      <div class="protocol-form__head">
        <div>
          <strong>{{ t('protocol.awgMeshParams') }}</strong>
          <span>{{ t('protocol.awgMeshParamsHint') }}</span>
        </div>
        <el-button :icon="Refresh" @click="randomizeAll">{{ t('protocol.randomAll') }}</el-button>
      </div>

      <div class="protocol-form__grid">
        <el-form-item v-for="field in sFields" :key="field" :label="field.replace('awg_', '').toUpperCase()">
          <el-input-number v-model="model[field]" :min="field === 'awg_s4' ? 0 : 0" :max="field === 'awg_s4' ? 32 : 64" style="width: 100%" />
          <el-button class="protocol-form__random" :icon="Refresh" @click="randomizeOne(field)" />
        </el-form-item>
        <el-form-item v-for="field in hFields" :key="field" :label="field.replace('awg_', '').toUpperCase()">
          <el-input v-model="model[field]" :placeholder="t('protocol.hPlaceholder')" />
          <el-button class="protocol-form__random" :icon="Refresh" @click="randomizeOne(field)" />
        </el-form-item>
      </div>
    </section>
  </div>
</template>

<style scoped>
.protocol-form { display: grid; gap: 12px; }
.protocol-form__awg { display: grid; gap: 14px; padding: 14px; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface-sunken); }
.protocol-form__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.protocol-form__head strong,
.protocol-form__head span { display: block; }
.protocol-form__head strong { color: var(--app-text); }
.protocol-form__head span { margin-top: 4px; color: var(--app-muted); font-size: 13px; }
.protocol-form__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 12px; }
.protocol-form__random { margin-top: 8px; width: 100%; }
@media (max-width: 720px) {
  .protocol-form__head { flex-direction: column; align-items: stretch; }
  .protocol-form__grid { grid-template-columns: 1fr; }
}
</style>
