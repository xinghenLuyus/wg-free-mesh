<script setup lang="ts">
import { computed, reactive } from 'vue'
import { useI18n } from 'vue-i18n'

import type { NodeRead } from '@/types/api'

type PortForwardPlatform = 'linux' | 'darwin'

const props = defineProps<{
  nodes: NodeRead[]
  disabled?: boolean
}>()

const emit = defineEmits<{
  submit: [payload: {
    from_node_id: string
    from_port: number
    to_node_id: string
    to_port: number
    to_platform: PortForwardPlatform
    protocol: 'tcp' | 'udp' | 'all'
  }]
}>()

const { t } = useI18n()
const form = reactive({
  from_node_id: '',
  from_port: 80,
  to_node_id: '',
  to_port: 8080,
  to_platform: 'linux' as PortForwardPlatform,
  protocol: 'tcp' as 'tcp' | 'udp' | 'all',
})

const selectableNodes = computed(() => props.nodes.filter((node) => node.enabled && Boolean(node.virtual_ip)))
const fromNode = computed(() => selectableNodes.value.find((node) => node.id === form.from_node_id) || null)
const toNode = computed(() => selectableNodes.value.find((node) => node.id === form.to_node_id) || null)
const canSubmit = computed(() =>
  Boolean(
    fromNode.value
      && toNode.value
      && fromNode.value.id !== toNode.value.id
      && form.from_port > 0
      && form.to_port > 0,
  ),
)

function nodeLabel(node: NodeRead) {
  return `${node.name} (${node.virtual_ip || '-'})`
}

function submit() {
  if (!canSubmit.value) return
  emit('submit', {
    from_node_id: form.from_node_id,
    from_port: form.from_port,
    to_node_id: form.to_node_id,
    to_port: form.to_port,
    to_platform: form.to_platform,
    protocol: form.protocol,
  })
}
</script>

<template>
  <section class="port-forward-form">
    <div class="port-forward-form__head">
      <h2>{{ t('tools.portForward.createTitle') }}</h2>
      <p>{{ t('tools.portForward.createDescription') }}</p>
    </div>

    <el-form label-position="top" @submit.prevent>
      <div class="port-forward-form__pair">
        <section class="port-forward-form__endpoint">
          <strong>{{ t('tools.portForward.sourceTitle') }}</strong>
          <p>{{ t('tools.portForward.sourceDescription') }}</p>
          <el-form-item :label="t('tools.portForward.sourceNode')">
            <el-select v-model="form.from_node_id" :placeholder="t('tools.portForward.selectNode')" :disabled="disabled">
              <el-option v-for="node in selectableNodes" :key="node.id" :label="nodeLabel(node)" :value="node.id" />
            </el-select>
          </el-form-item>
          <div class="port-forward-form__grid">
            <el-form-item :label="t('tools.portForward.sourcePort')">
              <el-input-number v-model="form.from_port" :min="1" :max="65535" :disabled="disabled" />
            </el-form-item>
            <el-form-item :label="t('tools.portForward.protocol')">
              <el-select v-model="form.protocol" :disabled="disabled">
                <el-option label="TCP" value="tcp" />
                <el-option label="UDP" value="udp" />
                <el-option :label="t('tools.portForward.protocolAll')" value="all" />
              </el-select>
            </el-form-item>
          </div>
        </section>

        <section class="port-forward-form__endpoint">
          <strong>{{ t('tools.portForward.destinationTitle') }}</strong>
          <p>{{ t('tools.portForward.destinationDescription') }}</p>
          <el-form-item :label="t('tools.portForward.destinationNode')">
            <el-select v-model="form.to_node_id" :placeholder="t('tools.portForward.selectNode')" :disabled="disabled">
              <el-option v-for="node in selectableNodes" :key="node.id" :label="nodeLabel(node)" :value="node.id" />
            </el-select>
          </el-form-item>
          <div class="port-forward-form__grid">
            <el-form-item :label="t('tools.portForward.destinationPort')">
              <el-input-number v-model="form.to_port" :min="1" :max="65535" :disabled="disabled" />
            </el-form-item>
            <el-form-item :label="t('tools.portForward.destinationPlatform')">
              <el-select v-model="form.to_platform" :disabled="disabled">
                <el-option :label="t('tools.portForward.platformLinux')" value="linux" />
                <el-option :label="t('tools.portForward.platformDarwin')" value="darwin" />
              </el-select>
            </el-form-item>
          </div>
        </section>
      </div>

      <div class="port-forward-form__actions">
        <span>{{ t('tools.portForward.platformHint') }}</span>
        <el-button type="primary" :disabled="disabled || !canSubmit" @click="submit">{{ t('tools.portForward.createAction') }}</el-button>
      </div>
    </el-form>
  </section>
</template>

<style scoped>
.port-forward-form { display: grid; gap: 18px; padding: 24px; border: 1px solid var(--app-border); border-radius: 14px; background: var(--app-surface); box-shadow: var(--app-shadow-sm); }
.port-forward-form__head h2,
.port-forward-form__head p { margin: 0; }
.port-forward-form__head h2 { color: var(--app-text-strong); letter-spacing: 0; }
.port-forward-form__head p { margin-top: 6px; color: var(--app-muted); line-height: 1.65; }
.port-forward-form__pair { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
.port-forward-form__endpoint { display: grid; align-content: start; gap: 10px; padding: 16px; border: 1px solid var(--app-border); border-radius: 12px; background: var(--app-surface-elevated); }
.port-forward-form__endpoint strong { color: var(--app-text-strong); font-size: 18px; }
.port-forward-form__endpoint p { margin: 0; color: var(--app-muted); line-height: 1.55; }
.port-forward-form__grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.port-forward-form__actions { display: flex; align-items: center; justify-content: space-between; gap: 16px; padding-top: 2px; }
.port-forward-form__actions span { color: var(--app-muted); line-height: 1.55; }
:deep(.el-form-item) { margin-bottom: 0; }
:deep(.el-select),
:deep(.el-input-number) { width: 100%; }
@media (max-width: 960px) {
  .port-forward-form__pair,
  .port-forward-form__grid { grid-template-columns: 1fr; }
  .port-forward-form__actions { align-items: stretch; flex-direction: column; }
}
</style>
