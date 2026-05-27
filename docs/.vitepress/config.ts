import { defineConfig } from 'vitepress'
import { shared } from './config/shared'

export default defineConfig({
  ...shared,
  locales: {
    root: {
      label: '简体中文',
      lang: 'zh-CN',
      title: 'WG Free Mesh',
      description: '轻量化 WireGuard / AmneziaWG Mesh 管理平台',
      themeConfig: {
        siteTitle: 'WG Free Mesh',
        nav: [
          { text: '指南', link: '/guide/' },
          { text: '参考', link: '/reference/' },
          { text: '开发者', link: '/developer/' },
        ],
        outline: {
          label: '本页目录',
          level: [2, 3],
        },
        docFooter: {
          prev: '上一页',
          next: '下一页',
        },
        lastUpdated: {
          text: '最后更新',
        },
        returnToTopLabel: '回到顶部',
        sidebarMenuLabel: '菜单',
        darkModeSwitchLabel: '外观',
        lightModeSwitchTitle: '切换到浅色模式',
        darkModeSwitchTitle: '切换到深色模式',
      },
    },
    en: {
      label: 'English',
      lang: 'en-US',
      link: '/en/',
      title: 'WG Free Mesh',
      description: 'A lightweight WireGuard / AmneziaWG mesh management platform',
      themeConfig: {
        siteTitle: 'WG Free Mesh',
        nav: [
          { text: 'Guide', link: '/en/guide/' },
          { text: 'Reference', link: '/en/reference/' },
          { text: 'Developer', link: '/en/developer/' },
        ],
      },
    },
  },
})
