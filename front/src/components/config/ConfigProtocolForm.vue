<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { computed, onMounted, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'

import { api } from '@/api/modules'
import FieldHelpLabel from '@/components/common/FieldHelpLabel.vue'
import AwgOptionsForm from './AwgOptionsForm.vue'
import AwgNodeParamsForm from './AwgNodeParamsForm.vue'
import type { AwgVersion, AwgOptions, AwgNodeParams, NodeRead, ProtocolOptions } from '@/types/api'
import { notify } from '@/utils/notify'

export interface ConfigProtocolModel {
  tunnel_protocol: 'wireguard' | 'amneziawg'
  awg_version: AwgVersion | null
  awg_options: AwgOptions
  awg_s1: number | null
  awg_s2: number | null
  awg_s3: number | null
  awg_s4: number | null
  awg_h1: string | null
  awg_h2: string | null
  awg_h3: string | null
  awg_h4: string | null
  awg_node_updates?: Record<string, AwgNodeParams>
}

const props = withDefaults(defineProps<{ nodes?: NodeRead[] }>(), { nodes: () => [] })
const model = defineModel<ConfigProtocolModel>({ required: true })
const { t } = useI18n()

const protocolOptions = computed(() => [
  { label: 'WireGuard', value: 'wireguard' },
  { label: 'AmneziaWG', value: 'amneziawg' },
])

const options = shallowRef<ProtocolOptions | null>(null)
const changing = defineModel<boolean>('busy', { default: false })
const capabilities = computed(() => model.value.awg_version ? options.value?.versions[model.value.awg_version] : undefined)
const retainedOptions = shallowRef<AwgOptions>({ ...model.value.awg_options })

async function loadOptions() {
  try { options.value = await api.protocolOptions() }
  catch (error) { notify.error(error instanceof Error ? error.message : t('protocol.loadFailed')) }
}
onMounted(loadOptions)

async function changeVersion(target: AwgVersion) {
  changing.value = true
  try {
    const draftOptions = { ...retainedOptions.value, ...model.value.awg_options }
    const values = await api.convertAwgConfig({ ...model.value, awg_options: draftOptions, source_version: model.value.awg_version, awg_version: target })
    retainedOptions.value = { ...draftOptions, ...values.awg_options as AwgOptions }
    Object.assign(model.value, values, { awg_version: target })
    if (model.value.awg_node_updates && Object.keys(model.value.awg_node_updates).length) {
      model.value.awg_node_updates = {}
      selectedNode.value = ''
      notify.info(t('protocol.nodeDraftsReset'))
    }
    notify.info(t('protocol.versionApplied'))
  } catch (error) { notify.error(error instanceof Error ? error.message : t('protocol.loadFailed')) }
  finally { changing.value = false }
}

async function changeProtocol(value: string | number | boolean) {
  if (value === 'wireguard') {
    model.value.tunnel_protocol = 'wireguard'
    model.value.awg_version = null
    model.value.awg_node_updates = {}
    selectedNode.value = ''
    return
  }
  if (!options.value) await loadOptions()
  if (!options.value) return
  model.value.tunnel_protocol = 'amneziawg'
}

const sFields = ['awg_s1', 'awg_s2', 'awg_s3', 'awg_s4'] as const
const hFields = ['awg_h1', 'awg_h2', 'awg_h3', 'awg_h4'] as const
const sLabels = ['S1', 'S2', 'S3', 'S4'] as const
const hLabels = ['H1', 'H2', 'H3', 'H4'] as const

const direction = computed({
  get: () => String(model.value.awg_options._random_direction ?? 'generic'),
  set: (value: string) => { model.value.awg_options = { ...model.value.awg_options, _random_direction: value } },
})
const intensity = computed({
  get: () => String(model.value.awg_options._random_intensity ?? 'balanced'),
  set: (value: string) => { model.value.awg_options = { ...model.value.awg_options, _random_intensity: value } },
})
const selectedNode = shallowRef('')
function nodeParams(node: NodeRead): AwgNodeParams {
  return { awg_jc: node.awg_jc, awg_jmin: node.awg_jmin, awg_jmax: node.awg_jmax,
    awg_i1: node.awg_i1, awg_i2: node.awg_i2, awg_i3: node.awg_i3, awg_i4: node.awg_i4, awg_i5: node.awg_i5,
    awg_options: { ...node.awg_options } }
}
const selectedParams = computed<AwgNodeParams | null>({
  get: () => {
    const node = props.nodes.find((item) => item.id === selectedNode.value)
    return node ? model.value.awg_node_updates?.[node.id] ?? nodeParams(node) : null
  },
  set: (value) => {
    if (value) model.value.awg_node_updates = { ...model.value.awg_node_updates, [selectedNode.value]: value }
  },
})
// Create a detached draft before nested v-model edits; never mutate the loaded node.
function selectNode(id: string) {
  selectedNode.value = id
  if (selectedParams.value) selectedParams.value = selectedParams.value
}

async function randomizeAll() {
  changing.value = true
  try {
    const nodes = Object.fromEntries(props.nodes.map((node) => [node.id, model.value.awg_node_updates?.[node.id] ?? nodeParams(node)]))
    const values = await api.generateAwg({ awg_version: model.value.awg_version, direction: direction.value,
      intensity: intensity.value, config: model.value, nodes })
    Object.assign(model.value, values.config)
    if (props.nodes.length) model.value.awg_node_updates = values.nodes
    notify.info(t('protocol.generatedDraft'))
  } catch (error) {
    notify.error(error instanceof Error ? error.message : t('protocol.loadFailed'))
  } finally {
    changing.value = false
  }
}

async function regenerateKey() {
  changing.value = true
  try {
    const values = await api.randomAwgConfig('3.1', true)
    const options = values.awg_options as AwgOptions
    model.value.awg_options = { ...model.value.awg_options, header_protection_key: options.header_protection_key ?? null }
  } catch (error) { notify.error(error instanceof Error ? error.message : t('protocol.loadFailed')) }
  finally { changing.value = false }
}
</script>

<template>
  <div class="protocol-form">
    <el-form-item :label="t('protocol.protocol')">
      <el-segmented :model-value="model.tunnel_protocol" :options="protocolOptions" :disabled="changing" @update:model-value="changeProtocol" />
    </el-form-item>

    <section v-if="model.tunnel_protocol === 'amneziawg'" class="protocol-form__awg">
      <el-form-item :label="t('protocol.version')">
        <el-select :model-value="model.awg_version" :disabled="changing" :placeholder="t('protocol.selectVersion')" @update:model-value="changeVersion">
          <el-option v-for="version in options?.awg_versions ?? []" :key="version" :label="version" :value="version" />
        </el-select>
      </el-form-item>
      <p>{{ t('protocol.versionHint') }}</p>
      <template v-if="model.awg_version">
      <fieldset :disabled="changing" class="protocol-form__generator">
        <strong>{{ t('protocol.generator') }}</strong>
        <el-form-item :label="t('protocol.direction')">
          <el-select v-model="direction" :disabled="changing">
            <el-option v-for="value in ['generic', 'dns', 'stun', 'rtp', 'quic']" :key="value" :value="value" :label="t(`protocol.directions.${value}`)" />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('protocol.intensity')">
          <el-select v-model="intensity" :disabled="changing">
            <el-option v-for="value in ['low', 'balanced', 'high']" :key="value" :value="value" :label="t(`protocol.intensities.${value}`)" />
          </el-select>
        </el-form-item>
        <p>{{ t('protocol.generatorHint') }}</p>
        <el-button :icon="Refresh" :loading="changing" @click="randomizeAll">{{ t('protocol.generateAll') }}</el-button>
      </fieldset>
      <fieldset :disabled="changing" class="protocol-form__parameters">
      <div class="protocol-form__head">
        <div>
          <strong>{{ t('protocol.awgMeshParams') }}</strong>
          <span>{{ t('protocol.awgMeshParamsHint') }}</span>
        </div>
      </div>

      <div class="protocol-param-table">
        <div class="protocol-param-table__head">
          <span>{{ t('protocol.parameter') }}</span>
          <span>{{ t('protocol.value') }}</span>
        </div>
        <template v-for="(field, index) in sFields" :key="field">
        <div v-if="capabilities?.s_fields.includes(field)" class="protocol-param-table__row">
          <FieldHelpLabel :label="sLabels[index]" :help="t(`protocol.help.${field}`)" />
          <el-input-number v-model="model[field]" :min="0" :max="65535" :disabled="changing" class="protocol-param-table__control" />
        </div>
        </template>
        <div v-for="(field, index) in hFields" :key="field" class="protocol-param-table__row">
          <FieldHelpLabel :label="hLabels[index]" :help="t(`protocol.help.${field}`)" />
          <el-input v-model="model[field]" :disabled="changing" :placeholder="t(capabilities?.h_format === 'integer' ? 'protocol.hFixedPlaceholder' : 'protocol.hPlaceholder')" />
        </div>
      </div>
      <AwgOptionsForm v-if="capabilities" v-model="model.awg_options" :fields="capabilities.config_options" :disabled="changing" />
      <el-button v-if="capabilities?.config_options.header_protection_key" :disabled="changing" @click="regenerateKey">{{ t('protocol.regenerateKey') }}</el-button>
      <template v-if="nodes.length">
        <strong>{{ t('protocol.nodeParameters') }}</strong>
        <el-select :model-value="selectedNode" :disabled="changing" :placeholder="t('protocol.selectNode')" @update:model-value="selectNode">
          <el-option v-for="node in nodes" :key="node.id" :label="node.name" :value="node.id" />
        </el-select>
        <AwgNodeParamsForm v-if="selectedParams && capabilities" v-model="selectedParams" :fields="capabilities.node_options" :disabled="changing" />
      </template>
      </fieldset>
      </template>
    </section>
  </div>
</template>

<style scoped>
.protocol-form { display: grid; gap: 12px; }
.protocol-form__generator, .protocol-form__parameters { display: grid; gap: 12px; min-width: 0; margin: 0; padding: 0; border: 0; }
.protocol-form__generator { padding: 12px; border: 1px solid var(--app-border-soft); border-radius: 8px; }
.protocol-form__awg { display: grid; gap: 14px; padding: 14px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-elevated); box-shadow: var(--app-shadow-sm); }
.protocol-form__head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.protocol-form__head strong,
.protocol-form__head span { display: block; }
.protocol-form__head strong { color: var(--app-text); }
.protocol-form__head span { margin-top: 4px; color: var(--app-muted); font-size: 13px; }
.protocol-param-table { overflow: hidden; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface); }
.protocol-param-table__head,
.protocol-param-table__row { display: grid; grid-template-columns: 96px minmax(0, 1fr); align-items: center; gap: 12px; padding: 10px 12px; }
.protocol-param-table__head { background: var(--app-surface-sunken); color: var(--app-muted); font-size: 12px; font-weight: 700; }
.protocol-param-table__row + .protocol-param-table__row { border-top: 1px solid var(--app-border-soft); }
.protocol-param-table__control { width: 100%; }
@media (max-width: 720px) {
  .protocol-form__head { flex-direction: column; align-items: stretch; }
  .protocol-param-table__head { display: none; }
  .protocol-param-table__row { grid-template-columns: 1fr; align-items: stretch; }
}
</style>
