type TranslateFn = (key: string, params?: Record<string, unknown>) => string

function familyLabel(value: string) {
  return value.toUpperCase() === 'IPV6' ? 'IPv6' : 'IPv4'
}

export function translateMeshText(message: string, t: TranslateFn) {
  const value = String(message || '').trim()
  if (!value) return value

  let match = value.match(/^(.+) has no public (IPV4|IPV6) entry; auto mode leaves it empty$/i)
  if (match) return t('meshMessages.autoEndpointEmpty', { name: match[1], family: familyLabel(match[2]) })

  match = value.match(/^(.+) is missing virtual IP\. Forward AllowedIPs must be filled manually\.$/)
  if (match) return t('meshMessages.forwardAllowedIpsManual', { name: match[1] })

  match = value.match(/^(.+) is missing virtual IP\. Reverse AllowedIPs must be filled manually\.$/)
  if (match) return t('meshMessages.reverseAllowedIpsManual', { name: match[1] })

  match = value.match(/^(.+) has no public (IPV4|IPV6) entry\. Forward auto Endpoint will be empty\.$/i)
  if (match) return t('meshMessages.forwardEndpointEmpty', { name: match[1], family: familyLabel(match[2]) })

  match = value.match(/^(.+) has no public (IPV4|IPV6) entry\. Reverse auto Endpoint will be empty\.$/i)
  if (match) return t('meshMessages.reverseEndpointEmpty', { name: match[1], family: familyLabel(match[2]) })

  match = value.match(/^Mesh link between (.+) and (.+) is broken because both sides have no public endpoint\.$/)
  if (match) return t('meshMessages.brokenLink', { left: match[1], right: match[2] })

  match = value.match(/^Auto uses (.+)$/)
  if (match) return t('meshMessages.autoUses', { endpoint: match[1] })

  match = value.match(/^Manual uses (.+)$/)
  if (match) return t('meshMessages.manualUses', { endpoint: match[1] })

  match = value.match(/^Node (.+) has a self link\.$/)
  if (match) return t('meshMessages.selfLink', { node: match[1] })

  match = value.match(/^Link (.+) points to a missing node\.$/)
  if (match) return t('meshMessages.missingNode', { link: match[1] })

  match = value.match(/^Link (.+) is missing allowed_ips\.$/)
  if (match) return t('meshMessages.missingAllowedIps', { link: match[1] })

  if (value === 'Manual mode requires Host and Port') return t('meshMessages.manualNeedHostPort')
  if (value === 'Missing reverse link') return t('meshMessages.missingReverseLink')
  if (value === 'No Endpoint') return t('mesh.noneEndpoint')
  if (value === 'Current config has no peer links.') return t('meshMessages.noPeerLinks')
  if (value === 'Topology check passed.') return t('mesh.topologyOk')

  return value
}
