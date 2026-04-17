import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/components/layout/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const ApplyView = () => import('@/views/ApplyView.vue')
const ConfigOverviewView = () => import('@/views/ConfigOverviewView.vue')
const ConfigWorkspaceLayout = () => import('@/views/ConfigWorkspaceLayout.vue')
const DownloadConfigView = () => import('@/views/DownloadConfigView.vue')
const EndpointsView = () => import('@/views/EndpointsView.vue')
const HelpView = () => import('@/views/HelpView.vue')
const HomeView = () => import('@/views/HomeView.vue')
const LoginView = () => import('@/views/LoginView.vue')
const MeshView = () => import('@/views/MeshView.vue')
const NodeWorkspaceLayout = () => import('@/views/NodeWorkspaceLayout.vue')
const NodesView = () => import('@/views/NodesView.vue')
const SettingsView = () => import('@/views/SettingsView.vue')
const SetupView = () => import('@/views/SetupView.vue')
const SystemView = () => import('@/views/SystemView.vue')

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', component: LoginView },
    { path: '/setup', component: SetupView },
    {
      path: '/',
      component: AppLayout,
      children: [
        { path: '', component: HomeView },
        { path: 'configs', redirect: '/' },
        {
          path: 'configs/:configId',
          component: ConfigWorkspaceLayout,
          children: [
            { path: '', component: ConfigOverviewView },
            { path: 'nodes', component: NodesView },
            { path: 'mesh', redirect: (to) => `/configs/${to.params.configId}` },
            { path: 'apply', redirect: (to) => `/configs/${to.params.configId}` },
            { path: 'endpoints', redirect: (to) => `/configs/${to.params.configId}` },
            {
              path: 'nodes/:nodeId',
              component: NodeWorkspaceLayout,
              redirect: (to) => `/configs/${to.params.configId}/nodes/${to.params.nodeId}/mesh`,
              children: [
                { path: 'mesh', component: MeshView },
                { path: 'apply', component: ApplyView },
                { path: 'control', component: EndpointsView },
                { path: 'download', component: DownloadConfigView },
              ],
            },
          ],
        },
        { path: 'settings', component: SettingsView },
        { path: 'help', component: HelpView },
        { path: 'backups', redirect: '/settings' },
        { path: 'system', component: SystemView },
      ],
    },
  ],
})

router.beforeEach(async (to) => {
  const authStore = useAuthStore()
  const isSetupPage = to.path === '/setup'
  const isLoginPage = to.path === '/login'

  const state = await authStore.loadState()
  if (state?.setup_required) {
    return isSetupPage ? true : { path: '/setup' }
  }
  if (isSetupPage) {
    return authStore.authenticated ? { path: '/' } : { path: '/login' }
  }
  if (!authStore.authenticated && !isLoginPage) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
  if (authStore.authenticated && isLoginPage) {
    const redirect = typeof to.query.redirect === 'string' ? to.query.redirect : '/'
    return redirect
  }
  return true
})
