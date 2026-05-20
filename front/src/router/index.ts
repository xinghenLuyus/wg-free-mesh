import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/components/layout/AppLayout.vue'
import { useAuthStore } from '@/stores/auth'

const ApplyView = () => import('@/views/ApplyView.vue')
const ClientDownloadView = () => import('@/views/ClientDownloadView.vue')
const ConfigBulkDownloadView = () => import('@/views/ConfigBulkDownloadView.vue')
const ConfigOverviewView = () => import('@/views/ConfigOverviewView.vue')
const ConfigWorkspaceLayout = () => import('@/views/ConfigWorkspaceLayout.vue')
const DownloadConfigView = () => import('@/views/DownloadConfigView.vue')
const DownloadToolsView = () => import('@/views/DownloadToolsView.vue')
const EndpointsView = () => import('@/views/EndpointsView.vue')
const HelpView = () => import('@/views/HelpView.vue')
const HomeView = () => import('@/views/HomeView.vue')
const QuickMeshGenerateView = () => import('@/views/QuickMeshGenerateView.vue')
const QuickMeshToolsView = () => import('@/views/QuickMeshToolsView.vue')
const LoginView = () => import('@/views/LoginView.vue')
const MeshView = () => import('@/views/MeshView.vue')
const NodeAdvancedView = () => import('@/views/NodeAdvancedView.vue')
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
                { path: 'advanced', component: NodeAdvancedView },
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
        { path: 'tools/download', component: DownloadToolsView },
        { path: 'tools/download/client', component: ClientDownloadView },
        { path: 'tools/download/configs', component: ConfigBulkDownloadView },
        { path: 'tools/quick-mesh', component: QuickMeshToolsView },
        { path: 'tools/quick-mesh/hub-spoke', component: QuickMeshGenerateView, props: { mode: 'hub_spoke' } },
        { path: 'tools/quick-mesh/full-mesh', component: QuickMeshGenerateView, props: { mode: 'full_mesh' } },
        { path: 'tools/quick-mesh/free-mesh', component: QuickMeshGenerateView, props: { mode: 'free_mesh' } },
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
