// The API calls a non-admin an "operator", from when the website had an
// alert-review console. On the website today they are simply team members.
const ROLE_LABELS = { admin: 'Admin', operator: 'Member' }

export function roleLabel(role) {
  return ROLE_LABELS[role] ?? role
}
