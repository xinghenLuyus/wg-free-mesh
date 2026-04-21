<script setup lang="ts">
import en from 'element-plus/es/locale/lang/en'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { computed } from 'vue'
import { RouterView } from 'vue-router'

import { usePreferencesStore } from '@/stores/preferences'

const preferences = usePreferencesStore()
const elementLocale = computed(() => (preferences.locale === 'en-US' ? en : zhCn))
</script>

<template>
  <el-config-provider :locale="elementLocale">
    <RouterView v-slot="{ Component, route }">
      <Transition name="route-shell" appear>
        <component :is="Component" :key="route.matched[0]?.path || route.fullPath" />
      </Transition>
    </RouterView>
  </el-config-provider>
</template>
