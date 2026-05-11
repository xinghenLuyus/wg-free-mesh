<script setup lang="ts">
import { Download, Files } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const downloadEntries = computed(() => [
  {
    path: '/tools/download/client',
    title: t('tools.download.clientTitle'),
    description: t('tools.download.clientDescription'),
    action: t('tools.download.clientAction'),
    icon: Download,
  },
  {
    path: '/tools/download/configs',
    title: t('tools.download.configBulkTitle'),
    description: t('tools.download.configBulkDescription'),
    action: t('tools.download.configBulkAction'),
    icon: Files,
  },
])
</script>

<template>
  <section class="download-tools-page">
    <div class="download-tools-hero">
      <div>
        <p class="download-tools-hero__eyebrow">{{ t('layout.toolList') }}</p>
        <h1>{{ t('tools.download.title') }}</h1>
        <p>{{ t('tools.download.description') }}</p>
      </div>
      <el-icon><Download /></el-icon>
    </div>

    <div class="download-tools-grid">
      <RouterLink v-for="entry in downloadEntries" :key="entry.path" :to="entry.path" class="download-entry">
        <span class="download-entry__icon">
          <el-icon><component :is="entry.icon" /></el-icon>
        </span>
        <span class="download-entry__copy">
          <strong>{{ entry.title }}</strong>
          <span>{{ entry.description }}</span>
        </span>
        <span class="download-entry__action">{{ entry.action }}</span>
      </RouterLink>
    </div>
  </section>
</template>

<style scoped>
.download-tools-page { display: grid; gap: 18px; }
.download-tools-hero {
  display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 172px; padding: 32px;
  border: 1px solid var(--app-border); border-radius: 18px; background: linear-gradient(135deg, var(--app-surface) 0%, var(--app-surface-elevated) 100%);
  box-shadow: var(--app-shadow-sm);
}
.download-tools-hero__eyebrow { margin: 0 0 10px; color: var(--app-primary-strong); font-size: 12px; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }
.download-tools-hero h1 { margin: 0; color: var(--app-text-strong); font-size: 34px; letter-spacing: 0; }
.download-tools-hero p { max-width: 620px; margin: 10px 0 0; color: var(--app-muted); }
.download-tools-hero > .el-icon { flex: 0 0 auto; width: 86px; height: 86px; border-radius: 18px; color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 42px; }
.download-tools-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.download-entry {
  display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 18px; min-height: 220px; padding: 28px;
  border: 1px solid var(--app-border); border-radius: 14px; color: inherit; background: var(--app-surface); text-decoration: none;
  box-shadow: var(--app-shadow-sm); transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease, background-color 160ms ease;
}
.download-entry:hover { transform: translateY(-2px); border-color: var(--app-border-accent); background: var(--app-surface-elevated); box-shadow: var(--app-shadow-md); }
.download-entry:focus-visible { outline: 0; box-shadow: var(--app-focus), var(--app-shadow-md); }
.download-entry__icon {
  display: inline-flex; align-items: center; justify-content: center; width: 54px; height: 54px; border-radius: 12px;
  color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 28px;
}
.download-entry__copy { display: grid; align-content: start; gap: 10px; min-width: 0; }
.download-entry__copy strong { color: var(--app-text-strong); font-size: 24px; line-height: 1.2; letter-spacing: 0; }
.download-entry__copy span { color: var(--app-muted); line-height: 1.7; }
.download-entry__action {
  grid-column: 2; align-self: end; justify-self: start; color: var(--app-primary-strong); font-size: 13px; font-weight: 850;
}
@media (max-width: 960px) {
  .download-tools-hero { align-items: flex-start; padding: 24px; }
  .download-tools-hero > .el-icon { width: 64px; height: 64px; font-size: 32px; }
  .download-tools-grid { grid-template-columns: 1fr; }
  .download-entry { min-height: 180px; padding: 22px; }
}
</style>
