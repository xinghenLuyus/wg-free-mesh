<script setup lang="ts">
import { Delete, Plus } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

import type { PortForwardRuleRead } from '@/types/api'

defineProps<{
  rules: PortForwardRuleRead[]
  configNames: Record<string, string>
  disabled?: boolean
}>()

const emit = defineEmits<{
  create: []
  toggle: [rule: PortForwardRuleRead, enabled: boolean]
  remove: [rule: PortForwardRuleRead]
}>()
const { t } = useI18n()
</script>

<template>
  <section class="port-forward-list">
    <div class="port-forward-list__head">
      <div>
        <h2>{{ t('tools.portForward.rulesTitle') }}</h2>
        <p>{{ t('tools.portForward.rulesDescription') }}</p>
      </div>
      <el-button type="primary" :icon="Plus" :disabled="disabled" @click="emit('create')">{{ t('tools.portForward.newRule') }}</el-button>
    </div>

    <div v-if="!rules.length" class="port-forward-list__empty">{{ t('tools.portForward.noRules') }}</div>
    <div v-else class="port-forward-list__grid">
      <article v-for="rule in rules" :key="rule.id" class="port-forward-rule" :class="{ 'port-forward-rule--disabled': !rule.enabled }">
        <div class="port-forward-rule__route">
          <div class="port-forward-rule__endpoint">
            <span>From</span>
            <strong>{{ rule.from_node.name }}</strong>
            <em>{{ rule.from_node.virtual_ip }}:{{ rule.from_port }}</em>
          </div>
          <div class="port-forward-rule__flow">
            <b>{{ rule.protocol === 'all' ? t('tools.portForward.protocolAll') : rule.protocol.toUpperCase() }}</b>
            <i></i>
          </div>
          <div class="port-forward-rule__endpoint">
            <span>To</span>
            <strong>{{ rule.to_node.name }}</strong>
            <em>{{ rule.to_node.virtual_ip }}:{{ rule.to_port }}</em>
          </div>
        </div>

        <div class="port-forward-rule__meta">
          <el-tag effect="plain">{{ configNames[rule.config_id] || rule.config_id }}</el-tag>
          <el-tag effect="plain">{{ rule.to_platform === 'darwin' ? t('tools.portForward.platformDarwin') : t('tools.portForward.platformLinux') }}</el-tag>
        </div>

        <div class="port-forward-rule__actions">
          <label class="port-forward-rule__switch">
            <span>{{ rule.enabled ? t('tools.portForward.enabled') : t('tools.portForward.disabled') }}</span>
            <el-switch :model-value="rule.enabled" :disabled="disabled" @change="(value: string | number | boolean) => emit('toggle', rule, Boolean(value))" />
          </label>
          <el-button :icon="Delete" type="danger" plain :disabled="disabled" @click="emit('remove', rule)">
            {{ t('common.delete') }}
          </el-button>
        </div>
      </article>
    </div>
  </section>
</template>

<style scoped>
.port-forward-list { display: grid; gap: 16px; padding: 24px; border: 1px solid var(--app-border); border-radius: 14px; background: var(--app-surface); box-shadow: var(--app-shadow-sm); }
.port-forward-list__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 14px; }
.port-forward-list__head h2,
.port-forward-list__head p { margin: 0; }
.port-forward-list__head h2 { color: var(--app-text-strong); letter-spacing: 0; }
.port-forward-list__head p { margin-top: 6px; color: var(--app-muted); line-height: 1.65; }
.port-forward-list__empty { padding: 18px; border: 1px dashed var(--app-border); border-radius: 10px; color: var(--app-muted); background: var(--app-surface-elevated); }
.port-forward-list__grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(430px, 100%), 1fr)); gap: 14px; align-items: start; }
.port-forward-rule { display: grid; gap: 14px; padding: 16px; border: 1px solid var(--app-border); border-radius: 12px; background: var(--app-surface-elevated); }
.port-forward-rule--disabled { background: color-mix(in srgb, var(--app-surface-elevated) 72%, var(--app-surface-sunken)); }
.port-forward-rule__route { display: grid; grid-template-columns: minmax(0, 1fr) 92px minmax(0, 1fr); align-items: center; gap: 10px; }
.port-forward-rule__endpoint { display: grid; gap: 4px; min-width: 0; }
.port-forward-rule__endpoint span { color: var(--app-faint); font-size: 12px; font-weight: 800; }
.port-forward-rule__endpoint strong { overflow: hidden; color: var(--app-text-strong); text-overflow: ellipsis; white-space: nowrap; }
.port-forward-rule__endpoint em { overflow: hidden; color: var(--app-muted); font-size: 13px; font-style: normal; text-overflow: ellipsis; white-space: nowrap; }
.port-forward-rule__flow { display: grid; justify-items: center; gap: 7px; min-width: 0; }
.port-forward-rule__flow b { max-width: 100%; padding: 5px 8px; border-radius: 8px; color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 11px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.port-forward-rule__flow i { position: relative; display: block; width: 100%; height: 1px; background: var(--app-border-accent); }
.port-forward-rule__flow i::after { position: absolute; top: -4px; right: -1px; width: 8px; height: 8px; border-top: 1px solid var(--app-border-accent); border-right: 1px solid var(--app-border-accent); content: ''; transform: rotate(45deg); }
.port-forward-rule__meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; min-width: 0; }
.port-forward-rule__actions { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.port-forward-rule__switch { display: inline-flex; align-items: center; gap: 10px; color: var(--app-muted); font-size: 13px; font-weight: 700; }
@media (max-width: 720px) {
  .port-forward-list__head { align-items: stretch; flex-direction: column; }
  .port-forward-rule__route { grid-template-columns: 1fr; justify-items: stretch; }
  .port-forward-rule__flow { justify-items: start; width: 100%; }
  .port-forward-rule__flow i { width: 84px; }
  .port-forward-rule__actions { align-items: stretch; flex-direction: column; }
  .port-forward-rule__actions .el-button { width: 100%; }
}
</style>
