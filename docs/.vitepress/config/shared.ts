import type { UserConfig } from 'vitepress'
import { sidebar } from './sidebar'

const base = process.env.VITEPRESS_BASE || '/'

export const shared: UserConfig = {
  title: 'WG Free Mesh',
  titleTemplate: 'WFM - DOCS',
  base,
  cleanUrls: true,
  lastUpdated: true,
  head: [
    ['link', { rel: 'icon', href: `${base}favicon.ico` }],
    ['meta', { name: 'theme-color', content: '#2f8f8a' }],
  ],
  markdown: {
    lineNumbers: true,
  },
  themeConfig: {
    logo: { src: `${base}logo.png`, alt: 'WG Free Mesh' },
    sidebar,
    search: {
      provider: 'local',
      options: {
        locales: {
          root: {
            translations: {
              button: {
                buttonText: '搜索',
                buttonAriaLabel: '搜索',
              },
              modal: {
                noResultsText: '没有结果',
                resetButtonTitle: '清除查询',
                footer: {
                  selectText: '选择',
                  navigateText: '切换',
                  closeText: '关闭',
                },
              },
            },
          },
          en: {
            translations: {
              button: {
                buttonText: 'Search',
                buttonAriaLabel: 'Search',
              },
              modal: {
                noResultsText: 'No results found',
                resetButtonTitle: 'Reset search',
                footer: {
                  selectText: 'select',
                  navigateText: 'navigate',
                  closeText: 'close',
                },
              },
            },
          },
        },
      },
    },
    socialLinks: [
      { icon: 'github', link: 'https://github.com/xinghenLuyus/wg-free-mesh' },
    ],
  },
}
