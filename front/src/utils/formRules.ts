import type { FormItemRule } from 'element-plus'

function withDefaultTrigger(rule: FormItemRule, trigger: string | string[] = ['blur', 'change']): FormItemRule {
  return {
    ...rule,
    trigger,
  }
}

export function requiredTextRule(label: string): FormItemRule {
  return withDefaultTrigger({
    validator: (_rule, value: unknown, callback) => {
      if (typeof value !== 'string' || !value.trim()) {
        callback(new Error(`${label}不能为空`))
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
        callback(new Error(`${label}不能少于 ${minLength} 个字符`))
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
        callback(new Error(`请选择${label}`))
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
        callback(new Error(`请选择${label}`))
        return
      }
      callback()
    },
  })
}
