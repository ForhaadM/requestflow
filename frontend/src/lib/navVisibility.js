// Which roles see which nav tabs. Reviewers/admins don't meaningfully use
// "New Request" or "My Requests", so they're hidden for those roles here —
// flip this back on by adding the role to the relevant array.
export const NAV_VISIBILITY = {
  newRequest: ['requester'],
  myRequests: ['requester'],
}
