<script setup lang="ts">
import { QuestionFilled } from '@element-plus/icons-vue'

defineProps<{
  label: string
  help: string
}>()
</script>

<template>
  <span class="field-help-label">
    <span>{{ label }}</span>
    <el-tooltip :content="help" placement="top" :show-after="150" popper-class="field-help-popper">
      <el-icon class="field-help-label__icon"><QuestionFilled /></el-icon>
    </el-tooltip>
  </span>
</template>

<style scoped>
.field-help-label {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.field-help-label__icon {
  color: var(--app-faint);
  cursor: help;
  font-size: 14px;
}

.field-help-label__icon:hover {
  color: var(--app-primary);
}
</style>
