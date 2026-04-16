<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <RouterView v-slot="{ Component, route }">
    <Transition name="route-panel" appear>
      <component :is="Component" :key="route.matched[2]?.path || route.fullPath" />
    </Transition>
  </RouterView>
</template>
