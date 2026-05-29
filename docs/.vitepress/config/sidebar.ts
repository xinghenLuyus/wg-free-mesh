import type { DefaultTheme } from 'vitepress'

const zhGuideSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: '指南',
    items: [
      { text: '概览', link: '/guide/' },
      { text: '快速开始', link: '/guide/quick-start' },
      { text: '第一个 Mesh', link: '/guide/first-mesh' },
    ],
  },
  {
    text: '部署',
    collapsed: false,
    items: [
      { text: 'Docker 部署', link: '/deploy/' },
      { text: '环境变量', link: '/deploy/environment' },
      { text: '反向代理', link: '/deploy/reverse-proxy' },
    ],
  },
  {
    text: '功能',
    collapsed: false,
    items: [
      { text: '功能概览', link: '/usage/' },
      { text: '配置与端点', link: '/usage/configs' },
      { text: '客户端与控制', link: '/usage/client' },
      { text: '快速组网', link: '/usage/quick-mesh' },
      { text: '端口转发', link: '/usage/port-forward' },
      { text: '备份与恢复', link: '/usage/backups' },
      { text: 'AI 接入', link: '/ai/' },
    ],
  },
  {
    text: '帮助',
    collapsed: false,
    items: [
      { text: 'WG 环境安装', link: '/help/wg-environment' },
    ],
  },
]

const zhReferenceSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: '参考',
    items: [
      { text: '参考索引', link: '/reference/' },
      { text: '认证与权限', link: '/reference/auth' },
      { text: 'API', link: '/reference/api' },
      { text: 'MCP', link: '/reference/mcp' },
      { text: '实时事件', link: '/reference/realtime' },
      { text: 'MQTT 消息', link: '/reference/mqtt-messages' },
      { text: '客户端接入时序', link: '/reference/client-lifecycle' },
      { text: '下载与文件 token', link: '/reference/downloads' },
      { text: '快照', link: '/reference/snapshot' },
      { text: '数据模型', link: '/reference/data-model' },
      { text: '协议参数', link: '/reference/protocols' },
      { text: '快速组网', link: '/reference/quick-mesh' },
      { text: '安全边界', link: '/reference/security' },
      { text: '环境变量', link: '/reference/env' },
      { text: '错误码', link: '/reference/errors' },
    ],
  },
]

const zhDeveloperSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: '开发者',
    items: [
      { text: '开发者索引', link: '/developer/' },
      { text: '总体架构', link: '/developer/architecture' },
      { text: '目录与边界', link: '/developer/project-structure' },
      { text: '后端', link: '/developer/backend' },
      { text: '前端', link: '/developer/frontend' },
      { text: '客户端', link: '/developer/client' },
      { text: '数据库', link: '/developer/database' },
      { text: '实时事件', link: '/developer/events' },
      { text: 'MQTT 协议', link: '/developer/mqtt-protocol' },
      { text: 'API 契约', link: '/developer/api-contract' },
      { text: '协作约定', link: '/developer/collaboration' },
    ],
  },
]

const enGuideSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: 'Guide',
    items: [
      { text: 'Overview', link: '/en/guide/' },
      { text: 'Quick Start', link: '/en/guide/quick-start' },
      { text: 'First Mesh', link: '/en/guide/first-mesh' },
    ],
  },
  {
    text: 'Deploy',
    collapsed: false,
    items: [
      { text: 'Docker Deploy', link: '/en/deploy/' },
      { text: 'Environment', link: '/en/deploy/environment' },
      { text: 'Reverse Proxy', link: '/en/deploy/reverse-proxy' },
    ],
  },
  {
    text: 'Usage',
    collapsed: false,
    items: [
      { text: 'Overview', link: '/en/usage/' },
      { text: 'Configs and Nodes', link: '/en/usage/configs' },
      { text: 'Client and Control', link: '/en/usage/client' },
      { text: 'Quick Mesh', link: '/en/usage/quick-mesh' },
      { text: 'Port Forwarding', link: '/en/usage/port-forward' },
      { text: 'Backups', link: '/en/usage/backups' },
      { text: 'AI Integration', link: '/en/ai/' },
    ],
  },
  {
    text: 'Help',
    collapsed: false,
    items: [
      { text: 'WG Environment Install', link: '/en/help/wg-environment' },
    ],
  },
]

const enReferenceSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: 'Reference',
    items: [
      { text: 'Index', link: '/en/reference/' },
      { text: 'Auth', link: '/en/reference/auth' },
      { text: 'API', link: '/en/reference/api' },
      { text: 'MCP', link: '/en/reference/mcp' },
      { text: 'Realtime', link: '/en/reference/realtime' },
      { text: 'MQTT Messages', link: '/en/reference/mqtt-messages' },
      { text: 'Client Lifecycle', link: '/en/reference/client-lifecycle' },
      { text: 'Downloads', link: '/en/reference/downloads' },
      { text: 'Snapshots', link: '/en/reference/snapshot' },
      { text: 'Data Model', link: '/en/reference/data-model' },
      { text: 'Protocols', link: '/en/reference/protocols' },
      { text: 'Quick Mesh', link: '/en/reference/quick-mesh' },
      { text: 'Security', link: '/en/reference/security' },
      { text: 'Environment', link: '/en/reference/env' },
      { text: 'Errors', link: '/en/reference/errors' },
    ],
  },
]

const enDeveloperSidebar: DefaultTheme.SidebarItem[] = [
  {
    text: 'Developer',
    items: [
      { text: 'Index', link: '/en/developer/' },
      { text: 'Architecture', link: '/en/developer/architecture' },
      { text: 'Structure', link: '/en/developer/project-structure' },
      { text: 'Backend', link: '/en/developer/backend' },
      { text: 'Frontend', link: '/en/developer/frontend' },
      { text: 'Client', link: '/en/developer/client' },
      { text: 'Database', link: '/en/developer/database' },
      { text: 'Events', link: '/en/developer/events' },
      { text: 'MQTT Protocol', link: '/en/developer/mqtt-protocol' },
      { text: 'API Contract', link: '/en/developer/api-contract' },
      { text: 'Collaboration', link: '/en/developer/collaboration' },
    ],
  },
]

export const sidebar: DefaultTheme.Sidebar = {
  '/guide/': zhGuideSidebar,
  '/deploy/': zhGuideSidebar,
  '/usage/': zhGuideSidebar,
  '/ai/': zhGuideSidebar,
  '/help/': zhGuideSidebar,
  '/reference/': zhReferenceSidebar,
  '/developer/': zhDeveloperSidebar,
  '/en/guide/': enGuideSidebar,
  '/en/deploy/': enGuideSidebar,
  '/en/usage/': enGuideSidebar,
  '/en/ai/': enGuideSidebar,
  '/en/help/': enGuideSidebar,
  '/en/reference/': enReferenceSidebar,
  '/en/developer/': enDeveloperSidebar,
}
