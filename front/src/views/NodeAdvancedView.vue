<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import FieldHelpLabel from '@/components/common/FieldHelpLabel.vue'
import HookListEditor from '@/components/node/HookListEditor.vue'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
import type { ConfigRead, NodeRead } from '@/types/api'
import { toNodeUpdatePayload } from '@/utils/nodePayload'
import { notify } from '@/utils/notify'

const route = useRoute()
const { t } = useI18n()
const actions = useAsyncActionGroup()
const savingHooks = actions.isPending('save-node-hooks')
const savingAwg = actions.isPending('save-node-awg')
const randomizing = actions.isPending('random-awg-node')
const config = shallowRef<ConfigRead | null>(null)
const node = shallowRef<NodeRead | null>(null)
const loadError = shallowRef('')

const form = reactive({
  pre_up: [] as string[],
  post_up: [] as string[],
  pre_down: [] as string[],
  post_down: [] as string[],
  awg_jc: null as number | null,
  awg_jmin: null as number | null,
  awg_jmax: null as number | null,
  awg_i1: '',
  awg_i2: '',
  awg_i3: '',
  awg_i4: '',
  awg_i5: '',
})

const isAwg = computed(() => config.value?.tunnel_protocol === 'amneziawg_2')
const pageDescription = computed(() => t(isAwg.value ? 'nodeAdvanced.descriptionAwg' : 'nodeAdvanced.descriptionWireguard'))
const jFields = ['awg_jc', 'awg_jmin', 'awg_jmax'] as const
const jLabels = ['Jc', 'Jmin', 'Jmax'] as const
const iFields = ['awg_i1', 'awg_i2', 'awg_i3', 'awg_i4', 'awg_i5'] as const
const iLabels = ['I1', 'I2', 'I3', 'I4', 'I5'] as const

function fillForm(nextNode: NodeRead) {
  Object.assign(form, {
    pre_up: [...nextNode.pre_up],
    post_up: [...nextNode.post_up],
    pre_down: [...nextNode.pre_down],
    post_down: [...nextNode.post_down],
    awg_jc: nextNode.awg_jc,
    awg_jmin: nextNode.awg_jmin,
    awg_jmax: nextNode.awg_jmax,
    awg_i1: nextNode.awg_i1 || '',
    awg_i2: nextNode.awg_i2 || '',
    awg_i3: nextNode.awg_i3 || '',
    awg_i4: nextNode.awg_i4 || '',
    awg_i5: nextNode.awg_i5 || '',
  })
}

async function load() {
  loadError.value = ''
  try {
    const configId = String(route.params.configId)
    const nodeId = String(route.params.nodeId)
    const [configs, nextNode] = await Promise.all([api.configs(), api.node(nodeId)])
    config.value = configs.find((item) => item.id === configId) ?? null
    node.value = nextNode
    fillForm(nextNode)
  } catch (error) {
    loadError.value = error instanceof ApiClientError ? error.message : t('nodeAdvanced.loadFailed')
  }
}

async function randomizeAwg() {
  await actions.run('random-awg-node', async () => {
    const values = await api.randomAwgNode()
    Object.assign(form, values)
  })
}

async function randomizeAwgField(field: typeof jFields[number] | typeof iFields[number]) {
  await actions.run('random-awg-node', async () => {
    const values = await api.randomAwgNode()
    form[field] = values[field] as never
  })
}

async function saveHooks() {
  if (!node.value) return
  await actions.run('save-node-hooks', async () => {
    try {
      const pendingAwg = {
        awg_jc: form.awg_jc,
        awg_jmin: form.awg_jmin,
        awg_jmax: form.awg_jmax,
        awg_i1: form.awg_i1,
        awg_i2: form.awg_i2,
        awg_i3: form.awg_i3,
        awg_i4: form.awg_i4,
        awg_i5: form.awg_i5,
      }
      await api.updateNode(node.value!.id, toNodeUpdatePayload(node.value!, {
        pre_up: form.pre_up.filter(Boolean),
        post_up: form.post_up.filter(Boolean),
        pre_down: form.pre_down.filter(Boolean),
        post_down: form.post_down.filter(Boolean),
      }))
      await load()
      if (isAwg.value) {
        Object.assign(form, pendingAwg)
      }
      notify.success(t('nodeAdvanced.saved'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('nodeAdvanced.saveFailed'))
    }
  })
}

async function saveAwg() {
  if (!node.value) return
  await actions.run('save-node-awg', async () => {
    try {
      await api.updateNode(node.value!.id, toNodeUpdatePayload(node.value!, {
        awg_jc: form.awg_jc,
        awg_jmin: form.awg_jmin,
        awg_jmax: form.awg_jmax,
        awg_i1: form.awg_i1 || null,
        awg_i2: form.awg_i2 || null,
        awg_i3: form.awg_i3 || null,
        awg_i4: form.awg_i4 || null,
        awg_i5: form.awg_i5 || null,
      }))
      await load()
      notify.success(t('nodeAdvanced.saved'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('nodeAdvanced.saveFailed'))
    }
  })
}

watch(() => [route.params.configId, route.params.nodeId], load)
onMounted(load)
</script>

<template>
  <section class="node-advanced">
    <div v-if="loadError" class="view-feedback view-feedback--error">{{ loadError }}</div>
    <article v-else class="node-advanced-shell">
      <div class="node-advanced-shell__head">
        <div>
          <h2>{{ t('nodeAdvanced.title') }}</h2>
          <p>{{ pageDescription }}</p>
        </div>
      </div>

      <section class="node-param-section">
        <div class="node-param-section__head">
          <div>
            <h3>{{ t('nodeAdvanced.hookTitle') }}</h3>
            <p>{{ t('nodeAdvanced.hookDescription') }}</p>
          </div>
        </div>
        <div class="hook-grid">
          <HookListEditor v-model="form.pre_up" label="PreUp" :help="t('protocol.help.pre_up')" :applying="savingHooks" @apply="saveHooks" />
          <HookListEditor v-model="form.post_up" label="PostUp" :help="t('protocol.help.post_up')" :applying="savingHooks" @apply="saveHooks" />
          <HookListEditor v-model="form.pre_down" label="PreDown" :help="t('protocol.help.pre_down')" :applying="savingHooks" @apply="saveHooks" />
          <HookListEditor v-model="form.post_down" label="PostDown" :help="t('protocol.help.post_down')" :applying="savingHooks" @apply="saveHooks" />
        </div>
      </section>

      <section v-if="isAwg" class="node-param-section">
        <div class="node-param-section__head">
          <div>
            <h3>{{ t('nodeAdvanced.awgTitle') }}</h3>
            <p>{{ t('nodeAdvanced.awgDescription') }}</p>
          </div>
          <el-button :icon="Refresh" :loading="randomizing" @click="randomizeAwg">{{ t('protocol.randomAll') }}</el-button>
        </div>
        <div class="node-param-table">
          <div class="node-param-table__head">
            <span>{{ t('protocol.parameter') }}</span>
            <span>{{ t('protocol.value') }}</span>
            <span>{{ t('protocol.action') }}</span>
          </div>
          <div v-for="(field, index) in jFields" :key="field" class="node-param-table__row">
            <FieldHelpLabel :label="jLabels[index]" :help="t(`protocol.help.${field}`)" />
            <el-input-number v-model="form[field]" :min="field === 'awg_jc' ? 0 : 64" :max="field === 'awg_jc' ? 10 : 1024" class="node-param-table__control" />
            <el-button :icon="Refresh" :loading="randomizing" @click="randomizeAwgField(field)">{{ t('protocol.randomOne') }}</el-button>
          </div>
          <div v-for="(field, index) in iFields" :key="field" class="node-param-table__row">
            <FieldHelpLabel :label="iLabels[index]" :help="t(`protocol.help.${field}`)" />
            <el-input v-model="form[field]" type="textarea" :autosize="{ minRows: 1, maxRows: 4 }" />
            <el-button :icon="Refresh" :loading="randomizing" @click="randomizeAwgField(field)">{{ t('protocol.randomOne') }}</el-button>
          </div>
        </div>
        <div class="node-param-section__actions">
          <el-button type="primary" :loading="savingAwg" @click="saveAwg">{{ t('common.save') }}</el-button>
        </div>
      </section>
    </article>
  </section>
</template>

<style scoped>
.node-advanced { display: grid; gap: 16px; }
.node-advanced-shell { display: grid; gap: 20px; padding: 18px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-elevated); box-shadow: var(--app-shadow-sm); }
.node-advanced-shell__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.node-advanced-shell__head { padding-bottom: 16px; border-bottom: 1px solid var(--app-border-soft); }
.node-advanced-shell__head h2,
.node-advanced-shell__head p { margin: 0; }
.node-advanced-shell__head h2 { color: var(--app-text); }
.node-advanced-shell__head p { margin-top: 6px; color: var(--app-muted); line-height: 1.5; }
.hook-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.node-param-section { display: grid; gap: 14px; min-width: 0; }
.node-param-section + .node-param-section { padding-top: 18px; border-top: 1px solid var(--app-border-soft); }
.node-param-section__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; }
.node-param-section__head h3,
.node-param-section__head p { margin: 0; }
.node-param-section__head h3 { color: var(--app-text); }
.node-param-section__head p { margin-top: 6px; color: var(--app-muted); line-height: 1.5; }
.node-param-section__actions { display: flex; justify-content: flex-end; }
.node-param-table { overflow: hidden; border: 1px solid var(--app-border-soft); border-radius: 8px; background: var(--app-surface); }
.node-param-table__head,
.node-param-table__row { display: grid; grid-template-columns: 96px minmax(0, 1fr) 112px; align-items: center; gap: 12px; padding: 10px 12px; }
.node-param-table__head { background: var(--app-surface-sunken); color: var(--app-muted); font-size: 12px; font-weight: 700; }
.node-param-table__row + .node-param-table__row { border-top: 1px solid var(--app-border-soft); }
.node-param-table__control { width: 100%; }
.view-feedback { padding: 18px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-sunken); }
.view-feedback--error { border-color: var(--app-danger-border); color: var(--app-danger-text); }
@media (max-width: 720px) {
  .node-advanced-shell__head,
  .node-param-section__head { flex-direction: column; align-items: stretch; }
  .node-param-section__actions { justify-content: stretch; }
  .node-param-section__actions .el-button { width: 100%; }
  .hook-grid { grid-template-columns: 1fr; }
  .node-param-table__head { display: none; }
  .node-param-table__row { grid-template-columns: 1fr; align-items: stretch; }
}
</style>
