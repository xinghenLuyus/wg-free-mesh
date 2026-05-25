<script setup lang="ts">
import { ArrowLeft, CopyDocument, Delete, Key, Plus, RefreshRight, Search, SwitchButton } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { computed, onMounted, reactive, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'

import { ApiClientError } from '@/api/client'
import { api } from '@/api/modules'
import { useAsyncActionGroup } from '@/composables/useAsyncActionGroup'
import type { McpAuditRead, McpTokenRead } from '@/types/api'
import { formatDateTime } from '@/utils/dateTime'
import { notify } from '@/utils/notify'

const { t } = useI18n()
const router = useRouter()
const actions = useAsyncActionGroup()
const creating = actions.isPending('create-token')
const reloading = actions.isPending('reload')
const clearingAudit = actions.isPending('clear-audit')
const tokens = shallowRef<McpTokenRead[]>([])
const audit = shallowRef<McpAuditRead[]>([])
const createVisible = shallowRef(false)
const clearAuditVisible = shallowRef(false)
const form = reactive({
  name: '',
  permission: 'read' as 'read' | 'write',
  expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
})
const auditFilters = reactive({
  token_name: '',
  target_name: '',
  time_range: [] as string[],
  limit: 100,
})
const clearAuditRange = shallowRef<string[]>([])

const tokenCount = computed(() => tokens.value.filter((token) => !token.revoked_at).length)

function buildAuditQuery() {
  const [created_from, created_to] = auditFilters.time_range
  return {
    limit: auditFilters.limit,
    created_from,
    created_to,
    token_name: auditFilters.token_name.trim(),
    target_name: auditFilters.target_name.trim(),
  }
}

async function load() {
  await actions.run('reload', async () => {
    const [nextTokens, nextAudit] = await Promise.all([api.mcpTokens(), api.mcpAudit(buildAuditQuery())])
    tokens.value = nextTokens
    audit.value = nextAudit
  })
}

async function loadAudit() {
  try {
    audit.value = await api.mcpAudit(buildAuditQuery())
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('mcpAccess.auditLoadFailed'))
  }
}

async function resetAuditFilters() {
  Object.assign(auditFilters, {
    token_name: '',
    target_name: '',
    time_range: [],
    limit: 100,
  })
  await loadAudit()
}

function openCreate() {
  Object.assign(form, {
    name: '',
    permission: 'read',
    expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(),
  })
  createVisible.value = true
}

function backToOtherTools() {
  void router.push('/tools/other')
}

async function createToken() {
  await actions.run('create-token', async () => {
    try {
      await api.createMcpToken({ ...form })
      createVisible.value = false
      await load()
      notify.success(t('mcpAccess.tokenCreated'))
    } catch (error) {
      notify.error(error instanceof ApiClientError ? error.message : t('mcpAccess.tokenCreateFailed'))
    }
  })
}

async function revokeToken(token: McpTokenRead) {
  try {
    await api.revokeMcpToken(token.id)
    await load()
    notify.success(t('mcpAccess.tokenRevoked'))
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('mcpAccess.tokenRevokeFailed'))
  }
}

async function copyToken(token: string) {
  await navigator.clipboard.writeText(token)
  notify.success(t('mcpAccess.tokenCopied'))
}

function openClearAudit() {
  clearAuditRange.value = []
  clearAuditVisible.value = true
}

async function clearAudit() {
  const [created_from, created_to] = clearAuditRange.value
  if (!created_from || !created_to) {
    notify.warning(t('mcpAccess.clearAuditRangeRequired'))
    return
  }
  await actions.run('clear-audit', async () => {
    try {
      await ElMessageBox.confirm(t('mcpAccess.clearAuditConfirmMessage'), t('mcpAccess.clearAuditConfirmTitle'), {
        type: 'warning',
        confirmButtonText: t('common.confirm'),
        cancelButtonText: t('common.cancel'),
      })
      const result = await api.clearMcpAudit({ created_from, created_to })
      clearAuditVisible.value = false
      await loadAudit()
      notify.success(t('mcpAccess.auditCleared', { count: result.deleted_count }))
    } catch (error) {
      if (error === 'cancel' || error === 'close') {
        return
      }
      notify.error(error instanceof ApiClientError ? error.message : t('mcpAccess.auditClearFailed'))
    }
  })
}

onMounted(async () => {
  try {
    await load()
  } catch (error) {
    notify.error(error instanceof ApiClientError ? error.message : t('mcpAccess.loadFailed'))
  }
})
</script>

<template>
  <section class="mcp-page">
    <header class="mcp-hero">
      <div class="mcp-hero__copy">
        <el-button class="mcp-hero__back" :icon="ArrowLeft" plain @click="backToOtherTools">{{ t('mcpAccess.back') }}</el-button>
        <div>
          <p class="mcp-hero__eyebrow">{{ t('tools.other.title') }}</p>
          <h1>{{ t('mcpAccess.title') }}</h1>
          <p>{{ t('mcpAccess.description') }}</p>
        </div>
      </div>
      <div class="mcp-hero__actions">
        <el-tag type="info">{{ t('mcpAccess.activeTokens', { count: tokenCount }) }}</el-tag>
        <el-button :icon="RefreshRight" :loading="reloading" @click="load">{{ t('common.refresh') }}</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">{{ t('mcpAccess.createToken') }}</el-button>
      </div>
      <el-icon><Key /></el-icon>
    </header>

    <section class="mcp-panel">
      <div class="mcp-panel__head">
        <el-icon><Key /></el-icon>
        <div>
          <h2>{{ t('mcpAccess.tokens') }}</h2>
          <p>{{ t('mcpAccess.tokenDescription') }}</p>
        </div>
      </div>
      <el-table :data="tokens" row-key="id">
        <el-table-column prop="name" :label="t('fields.name')" min-width="150" />
        <el-table-column :label="t('mcpAccess.permission')" width="110">
          <template #default="{ row }">{{ t(`mcpAccess.permissions.${row.permission}`) }}</template>
        </el-table-column>
        <el-table-column prop="token" :label="t('mcpAccess.token')" min-width="300" show-overflow-tooltip />
        <el-table-column :label="t('mcpAccess.expiresAt')" min-width="170">
          <template #default="{ row }">{{ formatDateTime(row.expires_at) }}</template>
        </el-table-column>
        <el-table-column :label="t('mcpAccess.state')" width="110">
          <template #default="{ row }">
            <el-tag :type="row.revoked_at ? 'info' : 'success'">{{ row.revoked_at ? t('mcpAccess.revoked') : t('mcpAccess.active') }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="t('nodes.actions')" width="190">
          <template #default="{ row }">
            <el-space>
              <el-button size="small" :icon="CopyDocument" @click="copyToken(row.token)">{{ t('common.copy') }}</el-button>
              <el-button v-if="!row.revoked_at" size="small" type="danger" plain :icon="SwitchButton" @click="revokeToken(row)">
                {{ t('mcpAccess.revoke') }}
              </el-button>
            </el-space>
          </template>
        </el-table-column>
      </el-table>
    </section>

    <section class="mcp-panel">
      <div class="mcp-panel__head">
        <div>
          <h2>{{ t('mcpAccess.audit') }}</h2>
          <p>{{ t('mcpAccess.auditDescription') }}</p>
        </div>
      </div>
      <div class="mcp-audit-filter">
        <el-form class="mcp-audit-filter__form" label-position="top">
          <el-form-item :label="t('mcpAccess.time')">
            <el-date-picker
              v-model="auditFilters.time_range"
              type="datetimerange"
              value-format="YYYY-MM-DDTHH:mm:ssZ"
              :start-placeholder="t('mcpAccess.auditStartTime')"
              :end-placeholder="t('mcpAccess.auditEndTime')"
              style="width: 100%"
            />
          </el-form-item>
          <el-form-item :label="t('mcpAccess.auditName')">
            <el-input v-model="auditFilters.token_name" clearable :placeholder="t('mcpAccess.auditNamePlaceholder')" />
          </el-form-item>
          <el-form-item :label="t('mcpAccess.auditInterface')">
            <el-input v-model="auditFilters.target_name" clearable :placeholder="t('mcpAccess.auditInterfacePlaceholder')" />
          </el-form-item>
        </el-form>
        <div class="mcp-audit-filter__actions">
          <el-button :icon="Search" type="primary" @click="loadAudit">{{ t('mcpAccess.searchAudit') }}</el-button>
          <el-button @click="resetAuditFilters">{{ t('mcpAccess.resetAuditFilters') }}</el-button>
          <el-button :icon="Delete" type="danger" plain @click="openClearAudit">{{ t('mcpAccess.clearAudit') }}</el-button>
        </div>
      </div>
      <el-table :data="audit" row-key="id" empty-text="">
        <el-table-column :label="t('mcpAccess.time')" min-width="170">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column prop="token_name" :label="t('mcpAccess.tokenName')" min-width="140" />
        <el-table-column prop="target_name" :label="t('mcpAccess.target')" min-width="180" />
        <el-table-column prop="summary" :label="t('mcpAccess.summary')" min-width="220" show-overflow-tooltip />
        <el-table-column prop="result" :label="t('mcpAccess.result')" min-width="120" />
      </el-table>
    </section>

    <el-dialog v-model="createVisible" :title="t('mcpAccess.createToken')" width="520px">
      <el-form label-position="top">
        <el-form-item :label="t('fields.name')" required><el-input v-model="form.name" /></el-form-item>
        <el-form-item :label="t('mcpAccess.permission')" required>
          <el-segmented v-model="form.permission" :options="[
            { label: t('mcpAccess.permissions.read'), value: 'read' },
            { label: t('mcpAccess.permissions.write'), value: 'write' },
          ]" />
        </el-form-item>
        <el-form-item :label="t('mcpAccess.expiresAt')" required>
          <el-date-picker v-model="form.expires_at" type="datetime" value-format="YYYY-MM-DDTHH:mm:ssZ" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="primary" :loading="creating" @click="createToken">{{ t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="clearAuditVisible" :title="t('mcpAccess.clearAudit')" width="520px">
      <p class="mcp-dialog-copy">{{ t('mcpAccess.clearAuditDescription') }}</p>
      <el-form label-position="top">
        <el-form-item :label="t('mcpAccess.clearAuditRange')" required>
          <el-date-picker
            v-model="clearAuditRange"
            type="datetimerange"
            value-format="YYYY-MM-DDTHH:mm:ssZ"
            :start-placeholder="t('mcpAccess.auditStartTime')"
            :end-placeholder="t('mcpAccess.auditEndTime')"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="clearAuditVisible = false">{{ t('common.cancel') }}</el-button>
        <el-button type="danger" :loading="clearingAudit" @click="clearAudit">{{ t('mcpAccess.clearAudit') }}</el-button>
      </template>
    </el-dialog>
  </section>
</template>

<style scoped>
.mcp-page { display: grid; gap: 18px; }
.mcp-hero {
  display: grid; grid-template-columns: minmax(0, 1fr) auto auto; align-items: center; gap: 20px; min-height: 172px; padding: 28px 32px;
  border: 1px solid var(--app-border); border-radius: 18px; background: linear-gradient(135deg, var(--app-surface) 0%, var(--app-surface-elevated) 100%);
  box-shadow: var(--app-shadow-sm);
}
.mcp-panel { border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-surface); box-shadow: var(--app-shadow-sm); }
.mcp-hero__copy { display: grid; gap: 18px; min-width: 0; }
.mcp-hero__back { justify-self: start; }
.mcp-hero__eyebrow { margin: 0 0 10px; color: var(--app-primary-strong); font-size: 12px; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }
.mcp-hero p, .mcp-panel__head p { max-width: 660px; margin: 10px 0 0; color: var(--app-muted); line-height: 1.6; }
.mcp-hero h1 { margin: 0; color: var(--app-text-strong); font-size: 34px; letter-spacing: 0; }
.mcp-panel__head h2 { margin: 4px 0; color: var(--app-text-strong); letter-spacing: 0; }
.mcp-hero__actions { display: flex; align-items: center; flex-wrap: wrap; justify-content: flex-end; gap: 10px; }
.mcp-hero > .el-icon { flex: 0 0 auto; width: 86px; height: 86px; border-radius: 18px; color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 42px; }
.mcp-panel { display: grid; gap: 16px; padding: 20px; }
.mcp-panel__head { display: flex; align-items: center; gap: 12px; }
.mcp-panel__head > .el-icon { width: 42px; height: 42px; border-radius: 8px; background: var(--app-surface-selected); color: var(--app-primary-strong); font-size: 22px; }
.mcp-audit-filter {
  display: grid; gap: 12px; padding: 14px; border: 1px solid var(--app-border); border-radius: 8px; background: var(--app-bg);
}
.mcp-audit-filter__form {
  display: grid; grid-template-columns: minmax(280px, 1.25fr) minmax(180px, .8fr) minmax(180px, .8fr); gap: 12px;
}
.mcp-audit-filter__form :deep(.el-form-item) { margin-bottom: 0; }
.mcp-audit-filter__actions { display: flex; align-items: center; flex-wrap: wrap; gap: 10px; justify-content: flex-end; }
.mcp-dialog-copy { margin: 0 0 16px; color: var(--app-muted); line-height: 1.6; }
@media (max-width: 960px) {
  .mcp-hero { grid-template-columns: 1fr; align-items: stretch; }
  .mcp-hero__actions { justify-content: flex-start; }
  .mcp-hero > .el-icon { display: none; }
  .mcp-audit-filter__form { grid-template-columns: 1fr; }
  .mcp-audit-filter__actions { justify-content: flex-start; }
}
</style>
