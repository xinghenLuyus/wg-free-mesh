import type { FormItemRule } from 'element-plus'

import { hasTranslation, translate } from '@/i18n'

const FIELD_LABEL_KEYS: Record<string, string> = {
  用户名: 'fields.username',
  密码: 'fields.password',
  当前密码: 'fields.currentPassword',
  新密码: 'fields.newPassword',
  确认密码: 'fields.confirmPassword',
  名称: 'fields.name',
  '虚拟 IP': 'fields.virtualIp',
  Host: 'fields.host',
}

function withDefaultTrigger(rule: FormItemRule, trigger: string | string[] = ['blur', 'change']): FormItemRule {
  return {
    ...rule,
    trigger,
  }
}

function fieldLabel(label: string): string {
  const key = FIELD_LABEL_KEYS[label] || (label.includes('.') && hasTranslation(label) ? label : '')
  return key ? translate(key) : label
}

export function requiredTextRule(label: string): FormItemRule {
  return withDefaultTrigger({
    validator: (_rule, value: unknown, callback) => {
      if (typeof value !== 'string' || !value.trim()) {
        callback(new Error(translate('validation.required', { field: fieldLabel(label) })))
        return
      }
      callback()
    },
  })
}

export function minLengthTextRule(label: string, minLength: number): FormItemRule {
  return withDefaultTrigger({
    validator: (_rule, value: unknown, callback) => {
      if (typeof value !== 'string' || value.trim().length < minLength) {
        callback(new Error(translate('validation.minLength', { field: fieldLabel(label), min: minLength })))
        return
      }
      callback()
    },
  })
}

export function requiredSelectionRule(label: string): FormItemRule {
  return withDefaultTrigger({
    validator: (_rule, value: unknown, callback) => {
      if (typeof value !== 'string' || !value.trim()) {
        callback(new Error(translate('validation.requiredSelection', { field: fieldLabel(label) })))
        return
      }
      callback()
    },
  })
}

export function requiredArrayRule(label: string): FormItemRule {
  return withDefaultTrigger({
    validator: (_rule, value: unknown, callback) => {
      if (!Array.isArray(value) || !value.length) {
        callback(new Error(translate('validation.requiredSelection', { field: fieldLabel(label) })))
        return
      }
      callback()
    },
  })
}
