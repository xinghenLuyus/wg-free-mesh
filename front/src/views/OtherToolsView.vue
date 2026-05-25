<script setup lang="ts">
import { Connection, Key, SetUp } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const entries = computed(() => [
  {
    path: '/tools/other/mcp-access',
    title: t('tools.other.mcpAccessTitle'),
    description: t('tools.other.mcpAccessDescription'),
    action: t('tools.other.mcpAccessAction'),
    icon: Key,
  },
  {
    path: '/tools/other/port-forward',
    title: t('tools.other.portForwardTitle'),
    description: t('tools.other.portForwardDescription'),
    action: t('tools.other.portForwardAction'),
    icon: Connection,
  },
])
</script>

<template>
  <section class="other-tools-page">
    <div class="other-tools-hero">
      <div>
        <p class="other-tools-hero__eyebrow">{{ t('layout.toolList') }}</p>
        <h1>{{ t('tools.other.title') }}</h1>
        <p>{{ t('tools.other.description') }}</p>
      </div>
      <el-icon><SetUp /></el-icon>
    </div>

    <div class="other-tools-grid">
      <RouterLink v-for="entry in entries" :key="entry.path" :to="entry.path" class="other-tools-entry">
        <span class="other-tools-entry__icon">
          <el-icon><component :is="entry.icon" /></el-icon>
        </span>
        <span class="other-tools-entry__copy">
          <strong>{{ entry.title }}</strong>
          <span>{{ entry.description }}</span>
        </span>
        <span class="other-tools-entry__action">{{ entry.action }}</span>
      </RouterLink>
    </div>
  </section>
</template>

<style scoped>
.other-tools-page { display: grid; gap: 18px; }
.other-tools-hero {
  display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 172px; padding: 32px;
  border: 1px solid var(--app-border); border-radius: 18px; background: linear-gradient(135deg, var(--app-surface) 0%, var(--app-surface-elevated) 100%);
  box-shadow: var(--app-shadow-sm);
}
.other-tools-hero__eyebrow { margin: 0 0 10px; color: var(--app-primary-strong); font-size: 12px; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }
.other-tools-hero h1 { margin: 0; color: var(--app-text-strong); font-size: 34px; letter-spacing: 0; }
.other-tools-hero p { max-width: 620px; margin: 10px 0 0; color: var(--app-muted); }
.other-tools-hero > .el-icon { flex: 0 0 auto; width: 86px; height: 86px; border-radius: 18px; color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 42px; }
.other-tools-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.other-tools-entry {
  display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 18px; min-height: 220px; padding: 28px;
  border: 1px solid var(--app-border); border-radius: 14px; color: inherit; background: var(--app-surface); text-decoration: none;
  box-shadow: var(--app-shadow-sm); transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease, background-color 160ms ease;
}
.other-tools-entry:hover { transform: translateY(-2px); border-color: var(--app-border-accent); background: var(--app-surface-elevated); box-shadow: var(--app-shadow-md); }
.other-tools-entry:focus-visible { outline: 0; box-shadow: var(--app-focus), var(--app-shadow-md); }
.other-tools-entry__icon {
  display: inline-flex; align-items: center; justify-content: center; width: 54px; height: 54px; border-radius: 12px;
  color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 28px;
}
.other-tools-entry__copy { display: grid; align-content: start; gap: 10px; min-width: 0; }
.other-tools-entry__copy strong { color: var(--app-text-strong); font-size: 24px; line-height: 1.2; letter-spacing: 0; }
.other-tools-entry__copy span { color: var(--app-muted); line-height: 1.7; }
.other-tools-entry__action { grid-column: 2; align-self: end; justify-self: start; color: var(--app-primary-strong); font-size: 13px; font-weight: 850; }
@media (max-width: 960px) {
  .other-tools-hero { align-items: flex-start; padding: 24px; }
  .other-tools-hero > .el-icon { width: 64px; height: 64px; font-size: 32px; }
  .other-tools-grid { grid-template-columns: 1fr; }
  .other-tools-entry { min-height: 180px; padding: 22px; }
}
</style>
