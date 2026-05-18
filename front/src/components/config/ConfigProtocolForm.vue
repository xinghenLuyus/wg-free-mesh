<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import { api } from '@/api/modules'
import FieldHelpLabel from '@/components/common/FieldHelpLabel.vue'

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
const sLabels = ['S1', 'S2', 'S3', 'S4'] as const
const hLabels = ['H1', 'H2', 'H3', 'H4'] as const

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

      <div class="protocol-param-table">
        <div class="protocol-param-table__head">
          <span>{{ t('protocol.parameter') }}</span>
          <span>{{ t('protocol.value') }}</span>
          <span>{{ t('protocol.action') }}</span>
        </div>
        <div v-for="(field, index) in sFields" :key="field" class="protocol-param-table__row">
          <FieldHelpLabel :label="sLabels[index]" :help="t(`protocol.help.${field}`)" />
          <el-input-number v-model="model[field]" :min="0" :max="field === 'awg_s4' ? 32 : 64" class="protocol-param-table__control" />
          <el-button :icon="Refresh" @click="randomizeOne(field)">{{ t('protocol.randomOne') }}</el-button>
        </div>
        <div v-for="(field, index) in hFields" :key="field" class="protocol-param-table__row">
          <FieldHelpLabel :label="hLabels[index]" :help="t(`protocol.help.${field}`)" />
          <el-input v-model="model[field]" :placeholder="t('protocol.hPlaceholder')" />
          <el-button :icon="Refresh" @click="randomizeOne(field)">{{ t('protocol.randomOne') }}</el-button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.protocol-form { display: grid; gap: 12px; }
.protocol-form__awg { display: grid; gap: 14px; padding: 14px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-elevated); box-shadow: var(--app-shadow-sm); }
.protocol-form__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.protocol-form__head strong,
.protocol-form__head span { display: block; }
.protocol-form__head strong { color: var(--app-text); }
.protocol-form__head span { margin-top: 4px; color: var(--app-muted); font-size: 13px; }
.protocol-param-table { overflow: hidden; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface); }
.protocol-param-table__head,
.protocol-param-table__row { display: grid; grid-template-columns: 96px minmax(0, 1fr) 112px; align-items: center; gap: 12px; padding: 10px 12px; }
.protocol-param-table__head { background: var(--app-surface-sunken); color: var(--app-muted); font-size: 12px; font-weight: 700; }
.protocol-param-table__row + .protocol-param-table__row { border-top: 1px solid var(--app-border-soft); }
.protocol-param-table__control { width: 100%; }
@media (max-width: 720px) {
  .protocol-form__head { flex-direction: column; align-items: stretch; }
  .protocol-param-table__head { display: none; }
  .protocol-param-table__row { grid-template-columns: 1fr; align-items: stretch; }
}
</style>
