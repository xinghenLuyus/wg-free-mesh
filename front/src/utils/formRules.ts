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

function isValidIpv4Cidr(value: string) {
  const [address, prefixText] = value.split('/')
  if (!address || !prefixText) return false
  const octets = address.split('.')
  if (octets.length !== 4) return false
  if (!octets.every((item) => /^\d+$/.test(item) && Number(item) >= 0 && Number(item) <= 255)) return false
  if (!/^\d+$/.test(prefixText)) return false
  const prefix = Number(prefixText)
  return prefix >= 0 && prefix <= 32
}

function isValidIpv6Cidr(value: string) {
  const [address, prefixText] = value.split('/')
  if (!address || !prefixText) return false
  if (!/^[0-9a-fA-F:]+$/.test(address) || !address.includes(':')) return false
  if (!/^\d+$/.test(prefixText)) return false
  const prefix = Number(prefixText)
  return prefix >= 0 && prefix <= 128
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

export function cidrRule(label: string): FormItemRule {
  return withDefaultTrigger({
    validator: (_rule, value: unknown, callback) => {
      if (typeof value !== 'string' || !value.trim()) {
        callback(new Error(translate('validation.required', { field: fieldLabel(label) })))
        return
      }
      const normalized = value.trim()
      if (!isValidIpv4Cidr(normalized) && !isValidIpv6Cidr(normalized)) {
        callback(new Error(translate('validation.invalidCidr', { field: fieldLabel(label) })))
        return
      }
      callback()
    },
  })
}
