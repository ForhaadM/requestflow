const REQUEST_VERBS = { positiveAction: 'Approve', positiveLabel: 'Approved', negativeAction: 'Deny', negativeLabel: 'Denied' }
const ISSUE_VERBS = { positiveAction: 'Resolve', positiveLabel: 'Resolved', negativeAction: 'Decline', negativeLabel: 'Declined' }

export const REQUEST_TYPES = [
  {
    value: 'hardware',
    label: 'Hardware',
    examples: ['Laptop or monitor request', 'Broken keyboard or mouse', 'Docking station needed'],
    decisionVerbs: REQUEST_VERBS,
    requiresResolutionNotes: false,
  },
  {
    value: 'software',
    label: 'Software',
    examples: ['New software license', 'App installation request', 'Software upgrade'],
    decisionVerbs: REQUEST_VERBS,
    requiresResolutionNotes: false,
  },
  {
    value: 'access-request',
    label: 'Access Request',
    examples: ['VPN access', 'Shared drive/folder permissions', 'System or tool access'],
    decisionVerbs: REQUEST_VERBS,
    requiresResolutionNotes: false,
  },
  {
    value: 'account-password',
    label: 'Account / Password',
    examples: ['Password reset', 'Account locked out', 'MFA reset'],
    decisionVerbs: REQUEST_VERBS,
    requiresResolutionNotes: false,
  },
  {
    value: 'bug-report',
    label: 'Bug Report',
    examples: ['App crashing', 'Broken feature', 'Error message on a page'],
    decisionVerbs: ISSUE_VERBS,
    requiresResolutionNotes: true,
  },
  {
    value: 'network',
    label: 'Network / Connectivity',
    examples: ['Wi-Fi not working', 'Slow internet', 'VPN connection issues'],
    decisionVerbs: ISSUE_VERBS,
    requiresResolutionNotes: true,
  },
  {
    value: 'onboarding-offboarding',
    label: 'Onboarding / Offboarding',
    examples: ['New hire equipment setup', 'Account deprovisioning', 'Employee departure checklist'],
    decisionVerbs: REQUEST_VERBS,
    requiresResolutionNotes: false,
  },
  {
    value: 'facilities',
    label: 'Facilities',
    examples: ['Broken office equipment', 'Badge/access card issue', 'Conference room AV problem'],
    decisionVerbs: ISSUE_VERBS,
    requiresResolutionNotes: true,
  },
  {
    value: 'other',
    label: 'Other',
    examples: ["Anything that doesn't fit the categories above"],
    decisionVerbs: REQUEST_VERBS,
    requiresResolutionNotes: false,
  },
]

export function getTypeConfig(value) {
  return REQUEST_TYPES.find((t) => t.value === value)
}

export function requestTypeLabel(value) {
  return getTypeConfig(value)?.label || value
}

export function decisionVerbsFor(requestType) {
  return getTypeConfig(requestType)?.decisionVerbs || REQUEST_VERBS
}

export function decisionLabel(requestType, decision) {
  const verbs = decisionVerbsFor(requestType)
  return decision === 'APPROVED' ? verbs.positiveLabel : verbs.negativeLabel
}

// Shared by StatusBadge ('approved'/'rejected' request status) and
// DecisionBadge ('APPROVED'/'NOT APPROVED' review decision) so both reflect
// the same per-type verbiage (e.g. "Resolved" for a bug report).
export function outcomeLabel(requestType, outcome) {
  const verbs = decisionVerbsFor(requestType)
  return outcome === 'positive' ? verbs.positiveLabel : verbs.negativeLabel
}

export function requiresResolutionNotes(requestType) {
  return !!getTypeConfig(requestType)?.requiresResolutionNotes
}
