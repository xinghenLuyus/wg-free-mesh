import ElementPlus from 'element-plus'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import 'element-plus/dist/index.css'
import '@/assets/main.css'

import App from '@/App.vue'
import { i18n, setI18nLocale } from '@/i18n'
import { router } from '@/router'
import { applyThemeMode, readStoredLocale, readStoredThemeMode } from '@/stores/preferences'

setI18nLocale(readStoredLocale())
applyThemeMode(readStoredThemeMode())

createApp(App).use(createPinia()).use(router).use(i18n).use(ElementPlus).mount('#app')
