# Zondarr product context

Private Plex/Jellyfin invitations and member administration with a cinematic invitee onboarding flow.

## Platform

web

## Users

Public shell owner wordmark Home Cinema, Help, thin numbered progress; no admin navigation or Powered by footer. Invitee access summary is the final redemption receipt, not a persistent member account portal. Admin shell: 224px sidebar Dashboard, Invitations, Members, Servers, Wizards, Logs, Settings.

## Primary tasks

- **Invitee:** Invitation landing. Proposed route: `/join/MOVIENIGHT`.
- **Invitee:** House rules and required interaction. Proposed route: `/join/MOVIENIGHT/welcome`.
- **Invitee:** Plex join and access summary. Proposed route: `/join/MOVIENIGHT/account → /complete`.
- **Admin:** Admin community overview. Proposed route: `/admin`.
- **Admin:** Invitation list and editor. Proposed route: `/admin/invitations`.
- **Admin:** Member details and library access. Proposed route: `/admin/members/alex`.
- **Admin:** Wizard builder and preview. Proposed route: `/admin/wizards/house-rules`.
- **Admin:** Server and account settings. Proposed route: `/admin/settings`.

## Product requirements

- Admin accounts distinct from member accounts. Invitees join Plex/Jellyfin, not a new Zondarr account.
- Public views expose server names/types and permitted libraries, never server addresses, IDs, secrets or quiz answers.
- Used up differs from Expired. Invitation deletion preserves existing members.
- Plex joins through existing Plex account; Jellyfin may create username/password. No automatic email delivery.
- Member expiry enforcement is unimplemented in source; do not promise automatic removal. Wizard order enforced, required terms explicit.

## Confirmed visual direction

Golden Welcome × Velvet Premiere. A deliberate blend: Golden Welcome's warm gold arched light and soft geometric UI; Velvet Premiere's deep indigo, muted lavender and elegant serif display. Admin uses the same muted gold and indigo, flat and practical, with Outfit headings; serif reserved for public welcome and success. Gold primary, lavender informational. The selected direction is confirmed; these expanded layouts and exact token values are a proposed design seed for review.

## Accessibility and inclusion

Keyboard access throughout, visible focus, labelled inputs, text plus icon for status, 44px touch targets, readable text at 200% zoom, and reduced-motion alternatives. Target WCAG AA text contrast. Never use color alone to communicate a decision. Bundle fonts locally in the implementation.

## Product source and rewrite proposals

Read [the legacy product specification](docs/product/legacy-spec.md) for domain behavior and current gaps. Routes in this handoff describe proposed information architecture, not implemented endpoints.

Editing an existing server with a successful re-test is a proposed rewrite improvement. A persistent member portal, email delivery and enforced automatic member expiry are not introduced here.
