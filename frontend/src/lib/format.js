// The API calls a non-admin an "operator", from when the website had an
// alert-review console. On the website today they are simply team members.
const ROLE_LABELS = { admin: 'Admin', operator: 'Member' }

export function roleLabel(role) {
  return ROLE_LABELS[role] ?? role
}

// Plan ids are kept stable in the database; the names customers see changed
// when plans moved to cameras ("starter" is sold as Home).
const PLAN_LABELS = { free: 'Free', trial: 'Free trial', starter: 'Home', pro: 'Pro' }

export function planLabel(plan) {
  return PLAN_LABELS[plan] ?? plan
}
