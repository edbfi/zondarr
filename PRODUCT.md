# Zondarr product context

<!-- impeccable:product-schema 1 -->

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

## Positioning

Zondarr is the front door to an owner's private Plex and Jellyfin servers, and its scope is strictly membership: who gets an account, on which servers, with which libraries, for how long, and after agreeing to what. It sits beside the media servers as a peer of tools such as Wizarr or Overseerr-style request managers, but it does not manage media, requests, downloads, subtitles, playback or transcoding, and it sends no email or notifications.

The mechanism the record supports:

- One invitation code and link can grant accounts on several servers of either product at once. Each provider declares its capabilities, join style and permissions, so no screen hard-codes Plex or Jellyfin (D12, D19).
- The owner can require a reusable welcome wizard (house rules, terms, a timed read, a quiz) that the invitee must finish before an account exists. The server enforces the step order and completion with signed tokens, and quiz answers never reach the browser.
- Plex members get a direct library share with their own Plex account and no friend request to accept, because a pending friend request was the biggest drop-off in Plex onboarding.
- The public join page belongs to the owner's community, not to the tool: it carries no "Powered by Zondarr" footer, and invitees never sign in to Zondarr.

## Operating Context

- **Deployment:** one self-hosted instance per owner, run as one container, one process and one HTTP port, with the database file on a persistent volume; container packaging lives in the separate `zondarr-docker` repository (D4, D5). It runs on a trusted network or behind a reverse proxy; if a proxy rewrites the host, `sign-in`'s Module notes in [docs/SPEC.md](docs/SPEC.md) explain when `ORIGIN` or a proxy fix is needed.
- **Scale:** one owner's servers (typically one to a few), hundreds to low thousands of members and dozens of invitations.
- **Roles:** one owner account, the only administrator (there are no co-administrators), invitees who only ever see the public join page, and the operator who deploys the instance and whose environment settings lock the matching console settings.
- **How an invitation travels:** the admin copies the invite link and shares it out of band, since Zondarr sends no email. Codes are also read aloud and typed by hand, which is why generated codes avoid ambiguous characters (route-admin-invitations brief).
- **Devices:** the whole join flow must work on a phone as well as on a computer. The record makes no claim about which devices invitees actually use.
- **What happens after joining:** the invitee leaves Zondarr for their Plex or Jellyfin apps. The completion page is a receipt with a next step such as installing a Plex player, not a member portal (route-join-code-complete brief).
- **Background work:** Zondarr polls the media servers. Library and user sync, invitation expiry and session cleanup run unattended as in-process jobs, and there are no webhooks (D7).
- **Project state:** the legacy app shipped and was used by its author but was never formally released. The rewrite has only its ground floor: no database, authentication, providers or product modules yet (docs/SPEC.md). Routes in the surface briefs are proposed information architecture.

## Product requirements

- Admin accounts distinct from member accounts. Invitees join Plex/Jellyfin, not a new Zondarr account.
- Public views expose server names/types and permitted libraries, never server addresses, IDs, secrets or quiz answers.
- Used up differs from Expired. Invitation deletion preserves existing members.
- Plex joins through existing Plex account; Jellyfin may create username/password. No automatic email delivery.
- Member expiry follows the owner's policy: disable by default, delete only if the owner chooses it. The invitation shows what will happen at expiry. Wizard order enforced, required terms explicit.
- Privacy: Zondarr stores members' usernames, their account ids on each server, optional emails and Plex relationship types, and no media activity. For the owner it stores the link to their OIDC account and, encrypted, the media servers' API keys, the OIDC client secret and the two-factor secret. It never stores a member's password. An invitee's Plex sign-in token is kept only until the join uses it, and is deleted when its ten-minute sign-in window ends. It talks only to the media servers, Plex's account service and the owner's OIDC provider, if one is connected.
- Copy is plain, direct and in the second person, in short full sentences. A destructive confirmation says it can't be undone, and an empty state pairs a short title with one sentence on how the list fills. Labels and headings use sentence case, as DESIGN.md sets for titles. The admin console explains or avoids technical terms such as circuit breaker, environment variable and event stream. These rules are written for English; Danish keeps their intent.

## Confirmed visual direction

Golden Welcome × Velvet Premiere. A deliberate blend: Golden Welcome's warm gold arched light and soft geometric UI; Velvet Premiere's deep indigo, muted lavender and elegant serif display. Admin uses the same muted gold and indigo, flat and practical, with Outfit headings; serif reserved for public welcome and success. Gold primary, lavender informational. The selected direction is confirmed; these expanded layouts and exact token values are a proposed design seed for review.

## Evidence on Hand

What exists:

- **The legacy app's code:** the `legacy-old/v1` branch, for reference only; nothing is ported from it (AGENTS.md).
- **Decisions and ground-floor spec:** [docs/decisions.md](docs/decisions.md) and [docs/SPEC.md](docs/SPEC.md).
- **Upstream notes:** [docs/research/plex.md](docs/research/plex.md) and [docs/research/jellyfin.md](docs/research/jellyfin.md), how Plex and Jellyfin behaved for the legacy app, not re-verified.
- **Design mockups:** ten generated screens in `docs/design/screens/`, `01-public-invitation.webp` through `10-recovery-and-components.webp`, covering the invitee flow, a 390px mobile board, the admin console and a states-and-components board. They are composition references; their text is illustrative, and the surface briefs' raster corrections win (DESIGN.md).
- **Direction references:** `docs/design/references/golden-welcome.webp` and `docs/design/references/velvet-premiere.webp`, the two references the confirmed direction blends.
- **Surface briefs:** nine proposed briefs in `.impeccable/surfaces/`, one per route, five admin and four invitee.
- **Demo data:** [tests/fixtures/demo-fixtures.json](tests/fixtures/demo-fixtures.json) is fictional. It and the names in the briefs are the canonical demo content.
- **Identity asset:** `static/zondarr-logo.svg`, used in the README and as the favicon.
- **Licence:** AGPL-3.0, in `LICENSE`.

What does not exist, and must not be fabricated:

- No real members, communities, customers, testimonials, case studies, press or quotes. The fixture and brief names are fictional and must never be presented as real usage.
- No usage numbers, benchmarks, analytics or uptime figures. The legacy app was dogfooded by its author, but nothing quantifies that.
- No release, version number or changelog for either the legacy app or the rewrite. No hosted service, pricing or plans exist (the invitee brief rules out public pricing).
- No screenshots of the legacy app (none on `main` or `legacy-old/v1`) and none of rewrite screens; the mockups are generated design seeds, not captures of working software.
- No approved Plex or Jellyfin brand marks in the repo (DESIGN.md says not to reproduce generated connector logos).
- No user research or interviews.
- No email delivery, notifications or persistent member portal; copy must not imply them.

## Product Principles

1. **The owner's door, not the tool's.** The public flow speaks for the owner's community, and invitees never get a Zondarr account or see admin concerns. Each audience sees only what its job needs (Product requirements above).
2. **Membership, and nothing else.** Zondarr decides who gets in, where, to what, for how long and after agreeing to what. Media, requests, playback and messaging belong to other tools; a new capability has to serve membership to belong here.
3. **Tell the true state.** Show the real reason a code fails, make a failed share visible instead of quietly downgrading it, and never claim behaviour that isn't built (route-admin and route-admin-members-id briefs).
4. **Safe to run unattended.** Background work is idempotent and destructive only by the owner's explicit policy: sync reports stale members instead of deleting them, deleting an invitation or wizard never removes members, expiry disables a member unless the owner chose deletion, and an account is created exactly once (D7, D23).
5. **No product is special-cased.** Plex and Jellyfin are providers that declare what they can do, so a new server platform means a new provider, not new screens (D12, D19; AGENTS.md).

## Accessibility and inclusion

Target WCAG 2.2 AA. Keyboard access throughout, a skip link to the main content, visible focus, labelled inputs, labels on icon-only controls, menu and drawer buttons that state whether they're open, the current page marked in navigation, status and alert roles on empty and error states, a live region for wizard progress, autocomplete and one-time-code hints on inputs, text plus icon for status, 44px touch targets, readable text at 200% zoom, and reduced-motion alternatives. Never use color alone to communicate a decision. Bundle fonts locally in the implementation.
