import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import 'element-plus/dist/index.css'
import '@/assets/main.css'

import App from '@/App.vue'
import { router } from '@/router'

createApp(App).use(createPinia()).use(router).use(ElementPlus, { locale: zhCn }).mount('#app')

