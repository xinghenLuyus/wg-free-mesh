<script setup lang="ts">
import { shallowRef, watch } from 'vue'
import { RouterView } from 'vue-router'
import type { RouteLocationNormalizedLoaded } from 'vue-router'

import { completePageFadeOut } from '@/router/navigationProgress'

const props = defineProps<{ workspaceRoute: RouteLocationNormalizedLoaded }>()
const configId = String(props.workspaceRoute.params.configId)
const displayedRoute = shallowRef(props.workspaceRoute)

watch(() => props.workspaceRoute, (next) => {
  if (String(next.params.configId) === configId) displayedRoute.value = next
})
</script>

<template>
  <div class="route-stage">
    <RouterView :route="displayedRoute" v-slot="{ Component, route }">
      <Transition name="route-panel" @after-leave="completePageFadeOut">
        <div :key="`${route.matched[2]?.path || route.path}:${String(route.params.nodeId || '')}`" class="route-page">
          <component :is="Component" />
        </div>
      </Transition>
    </RouterView>
  </div>
</template>
