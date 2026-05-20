<script setup lang="ts">
import { Connection, Files, Share } from '@element-plus/icons-vue'
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const quickMeshEntries = computed(() => [
  {
    path: '/tools/quick-mesh/hub-spoke',
    title: t('tools.quickMesh.hubSpokeTitle'),
    description: t('tools.quickMesh.hubSpokeDescription'),
    action: t('tools.quickMesh.hubSpokeAction'),
    icon: Connection,
  },
  {
    path: '/tools/quick-mesh/full-mesh',
    title: t('tools.quickMesh.fullMeshTitle'),
    description: t('tools.quickMesh.fullMeshDescription'),
    action: t('tools.quickMesh.fullMeshAction'),
    icon: Files,
  },
  {
    path: '/tools/quick-mesh/free-mesh',
    title: t('tools.quickMesh.freeMeshTitle'),
    description: t('tools.quickMesh.freeMeshDescription'),
    action: t('tools.quickMesh.freeMeshAction'),
    icon: Share,
  },
])
</script>

<template>
  <section class="quick-mesh-page">
    <div class="quick-mesh-hero">
      <div>
        <p class="quick-mesh-hero__eyebrow">{{ t('layout.toolList') }}</p>
        <h1>{{ t('tools.quickMesh.title') }}</h1>
        <p>{{ t('tools.quickMesh.description') }}</p>
      </div>
      <el-icon><Connection /></el-icon>
    </div>

    <div class="quick-mesh-grid">
      <RouterLink v-for="entry in quickMeshEntries" :key="entry.path" :to="entry.path" class="quick-mesh-entry">
        <span class="quick-mesh-entry__icon">
          <el-icon><component :is="entry.icon" /></el-icon>
        </span>
        <span class="quick-mesh-entry__copy">
          <strong>{{ entry.title }}</strong>
          <span>{{ entry.description }}</span>
        </span>
        <span class="quick-mesh-entry__action">{{ entry.action }}</span>
      </RouterLink>
    </div>
  </section>
</template>

<style scoped>
.quick-mesh-page { display: grid; gap: 18px; }
.quick-mesh-hero {
  display: flex; align-items: center; justify-content: space-between; gap: 20px; min-height: 172px; padding: 32px;
  border: 1px solid var(--app-border); border-radius: 18px; background: linear-gradient(135deg, var(--app-surface) 0%, var(--app-surface-elevated) 100%);
  box-shadow: var(--app-shadow-sm);
}
.quick-mesh-hero__eyebrow { margin: 0 0 10px; color: var(--app-primary-strong); font-size: 12px; font-weight: 850; letter-spacing: .08em; text-transform: uppercase; }
.quick-mesh-hero h1 { margin: 0; color: var(--app-text-strong); font-size: 34px; letter-spacing: 0; }
.quick-mesh-hero p { max-width: 620px; margin: 10px 0 0; color: var(--app-muted); }
.quick-mesh-hero > .el-icon { flex: 0 0 auto; width: 86px; height: 86px; border-radius: 18px; color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 42px; }
.quick-mesh-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.quick-mesh-entry {
  display: grid; grid-template-columns: auto minmax(0, 1fr); gap: 18px; min-height: 220px; padding: 28px;
  border: 1px solid var(--app-border); border-radius: 14px; color: inherit; background: var(--app-surface); text-decoration: none;
  box-shadow: var(--app-shadow-sm); transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease, background-color 160ms ease;
}
.quick-mesh-entry:hover { transform: translateY(-2px); border-color: var(--app-border-accent); background: var(--app-surface-elevated); box-shadow: var(--app-shadow-md); }
.quick-mesh-entry:focus-visible { outline: 0; box-shadow: var(--app-focus), var(--app-shadow-md); }
.quick-mesh-entry__icon {
  display: inline-flex; align-items: center; justify-content: center; width: 54px; height: 54px; border-radius: 12px;
  color: var(--app-primary-strong); background: var(--app-surface-selected); font-size: 28px;
}
.quick-mesh-entry__copy { display: grid; align-content: start; gap: 10px; min-width: 0; }
.quick-mesh-entry__copy strong { color: var(--app-text-strong); font-size: 24px; line-height: 1.2; letter-spacing: 0; }
.quick-mesh-entry__copy span { color: var(--app-muted); line-height: 1.7; }
.quick-mesh-entry__action {
  grid-column: 2; align-self: end; justify-self: start; color: var(--app-primary-strong); font-size: 13px; font-weight: 850;
}
@media (max-width: 960px) {
  .quick-mesh-hero { align-items: flex-start; padding: 24px; }
  .quick-mesh-hero > .el-icon { width: 64px; height: 64px; font-size: 32px; }
  .quick-mesh-grid { grid-template-columns: 1fr; }
  .quick-mesh-entry { min-height: 180px; padding: 22px; }
}
</style>
