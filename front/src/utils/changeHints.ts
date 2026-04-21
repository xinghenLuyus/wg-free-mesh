import { translate } from '@/i18n'
import type { ChangeHintRead } from '@/types/api'
import { notify } from '@/utils/notify'

function messageForHint(hint: ChangeHintRead) {
  switch (hint.code) {
    case 'NODE_ENDPOINTS_RECALCULATED':
      return translate('changeHints.nodeEndpointsRecalculated', {
        count: hint.count ?? 0,
        cleared: hint.cleared_keepalive_count ?? 0,
      })
    case 'VIRTUAL_IP_CHANGED_REVIEW_ALLOWED_IPS':
      return translate('changeHints.virtualIpChangedReviewAllowedIps', {
        count: hint.count ?? 0,
      })
    case 'CONFIG_ENDPOINTS_RECALCULATED':
      return translate('changeHints.configEndpointsRecalculated', {
        count: hint.count ?? 0,
      })
    default:
      return ''
  }
}

export function notifyChangeHints(hints: ChangeHintRead[] | undefined) {
  for (const hint of hints || []) {
    const message = messageForHint(hint)
    if (!message) continue
    if (hint.level === 'warning') {
      notify.warning(message)
      continue
    }
    notify.info(message)
  }
}
