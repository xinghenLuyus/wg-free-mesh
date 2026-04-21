<script setup lang="ts">
import { HelpFilled } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <section class="content-card">
    <h1 class="page-title">{{ t('help.title') }}</h1>
    <div class="placeholder">
      <div class="placeholder-icon"><el-icon><HelpFilled /></el-icon></div>
      <div class="placeholder-text">{{ t('help.placeholder') }}</div>
      <div class="placeholder-desc">{{ t('help.description') }}</div>
    </div>
  </section>
</template>

<style scoped>
.content-card {
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: linear-gradient(180deg, var(--app-surface-elevated) 0%, var(--app-surface) 100%);
  box-shadow: var(--app-shadow-md);
}

.page-title {
  margin: 0 0 24px;
  color: var(--app-text);
  font-size: 30px;
}

.placeholder {
  display: grid;
  justify-items: center;
  gap: 10px;
  min-height: 200px;
  align-content: center;
}

.placeholder-icon {
  display: grid;
  place-items: center;
  width: 52px;
  height: 52px;
  border: 1px solid var(--app-border-accent);
  border-radius: 8px;
  background: var(--app-primary-soft);
  color: var(--app-primary);
  font-size: 24px;
  font-weight: 700;
  box-shadow: var(--app-shadow-sm);
}

.placeholder-text {
  color: var(--app-text-strong);
  font-size: 16px;
  font-weight: 600;
}

.placeholder-desc {
  color: var(--app-faint);
}
</style>
