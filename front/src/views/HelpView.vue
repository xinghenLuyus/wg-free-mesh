<script setup lang="ts">
import { HelpFilled } from '@element-plus/icons-vue'
</script>

<template>
  <section class="content-card">
    <h1 class="page-title">帮助</h1>
    <div class="placeholder">
      <div class="placeholder-icon"><el-icon><HelpFilled /></el-icon></div>
      <div class="placeholder-text">帮助内容后续补充。</div>
      <div class="placeholder-desc">这里保留和旧版一致的页面入口与占位位置。</div>
    </div>
  </section>
</template>

<style scoped>
.content-card {
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: 8px;
  background: linear-gradient(180deg, #ffffff 0%, #f8fbf9 100%);
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
  border: 1px solid #bfe0da;
  border-radius: 8px;
  background: var(--app-primary-soft);
  color: var(--app-primary);
  font-size: 24px;
  font-weight: 700;
  box-shadow: var(--app-shadow-sm);
}

.placeholder-text {
  color: #213029;
  font-size: 16px;
  font-weight: 600;
}

.placeholder-desc {
  color: #70837c;
}
</style>
