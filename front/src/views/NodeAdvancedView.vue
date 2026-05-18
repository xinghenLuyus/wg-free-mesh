<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'
import { computed, onMounted, reactive, shallowRef, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import HookListEditor from '@/components/node/HookListEditor.vue'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
import type { ConfigRead, NodeRead } from '@/types/api'
import { toNodeUpdatePayload } from '@/utils/nodePayload'
import { notify } from '@/utils/notify'

const route = useRoute()
const { t } = useI18n()
const actions = useAsyncActionGroup()
const saving = actions.isPending('save-node-advanced')
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
const iFields = ['awg_i1', 'awg_i2', 'awg_i3', 'awg_i4', 'awg_i5'] as const

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

async function save() {
  if (!node.value) return
  await actions.run('save-node-advanced', async () => {
    try {
      await api.updateNode(node.value!.id, toNodeUpdatePayload(node.value!, {
        pre_up: form.pre_up.filter(Boolean),
        post_up: form.post_up.filter(Boolean),
        pre_down: form.pre_down.filter(Boolean),
        post_down: form.post_down.filter(Boolean),
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
    <template v-else>
      <div class="node-advanced__head">
        <div>
          <h2>{{ t('nodeAdvanced.title') }}</h2>
          <p>{{ t('nodeAdvanced.description') }}</p>
        </div>
        <el-button type="primary" :loading="saving" @click="save">{{ t('common.save') }}</el-button>
      </div>

      <div class="hook-grid">
        <HookListEditor v-model="form.pre_up" label="PreUp" />
        <HookListEditor v-model="form.post_up" label="PostUp" />
        <HookListEditor v-model="form.pre_down" label="PreDown" />
        <HookListEditor v-model="form.post_down" label="PostDown" />
      </div>

      <section v-if="isAwg" class="awg-node-panel">
        <div class="node-advanced__head node-advanced__head--compact">
          <div>
            <h3>{{ t('nodeAdvanced.awgTitle') }}</h3>
            <p>{{ t('nodeAdvanced.awgDescription') }}</p>
          </div>
          <el-button :icon="Refresh" :loading="randomizing" @click="randomizeAwg">{{ t('protocol.randomAll') }}</el-button>
        </div>
        <div class="awg-node-grid">
          <el-form-item label="Jc"><el-input-number v-model="form.awg_jc" :min="0" :max="10" style="width: 100%" /></el-form-item>
          <el-form-item label="Jmin"><el-input-number v-model="form.awg_jmin" :min="64" :max="1024" style="width: 100%" /></el-form-item>
          <el-form-item label="Jmax"><el-input-number v-model="form.awg_jmax" :min="64" :max="1024" style="width: 100%" /></el-form-item>
          <el-form-item v-for="field in iFields" :key="field" :label="field.replace('awg_', '').toUpperCase()">
            <el-input v-model="form[field]" />
          </el-form-item>
        </div>
      </section>
    </template>
  </section>
</template>

<style scoped>
.node-advanced { display: grid; gap: 16px; }
.node-advanced__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; padding: 16px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-elevated); box-shadow: var(--app-shadow-sm); }
.node-advanced__head--compact { padding: 0; border: 0; background: transparent; box-shadow: none; }
.node-advanced__head h2,
.node-advanced__head h3,
.node-advanced__head p { margin: 0; }
.node-advanced__head h2,
.node-advanced__head h3 { color: var(--app-text); }
.node-advanced__head p { margin-top: 6px; color: var(--app-muted); line-height: 1.5; }
.hook-grid,
.awg-node-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.awg-node-panel { display: grid; gap: 14px; padding: 16px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-elevated); box-shadow: var(--app-shadow-sm); }
.view-feedback { padding: 18px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface-sunken); }
.view-feedback--error { border-color: var(--app-danger-border); color: var(--app-danger-text); }
@media (max-width: 720px) {
  .node-advanced__head { flex-direction: column; align-items: stretch; }
  .hook-grid,
  .awg-node-grid { grid-template-columns: 1fr; }
}
</style>
