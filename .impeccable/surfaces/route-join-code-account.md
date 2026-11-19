---
version: 1
slug: "route-join-code-account"
primary_target: "route:/join/[code]/account"
related_targets: ["route:/join/MOVIENIGHT/account"]
---

# Zondarr Plex join

## Status

Proposed design seed for review. Mode: **operate**. Audience: **Invitee**. Proposed route: `/join/MOVIENIGHT/account`.

## Purpose and composition

Account authorization, followed by the access receipt (`route:/join/[code]/complete`). Generous whitespace, muted lavender information blocks.

## Visual reference

None yet. Use the shared [design system](../../DESIGN.md).

## Required content

'Use your Plex account.' 'Continue with Plex'. Waiting state 'Waiting for Plex sign-in…' and Cancel.

## Acceptance criteria

No Zondarr account/password for Plex. Never expose remote IDs or internal addresses.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json).
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Account states

Each is its own state of this route.

- Server unavailable: 'Home Cinema is unreachable.' Retry.
- Account field validation: Jellyfin username field error 'Use lowercase letters, numbers or underscores.'

Public error contains no internal URL or ID. No stack trace. Gold action, lavender info, rose error, disabled button unambiguous.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then check desktop and mobile and audit the required states.
