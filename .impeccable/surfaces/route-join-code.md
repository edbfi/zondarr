---
version: 1
slug: "route-join-code"
primary_target: "route:/join/[code]"
related_targets: ["route:/join/MOVIENIGHT"]
---

# Zondarr Invitation landing

## Status

Proposed design seed for review. Mode: **persuade**. Audience: **Invitee**. Proposed route: `/join/MOVIENIGHT`.

## Purpose and composition

Golden arched-light hero on velvet-indigo; editorial serif invitation headline, restrained owner header, concise invitation summary and primary action.

## Visual reference

None yet. Use the shared [design system](../../DESIGN.md).

## Required content

Home Cinema. 'Your invitation is ready.' 'Join the movie nights.' Movies and Shows library chips, 'Plex', 'Invitation valid', 'No access expiry'. Primary 'Continue'. Thin stages Invitation / House rules / Account. Help link.

## Acceptance criteria

No admin controls, server URLs, remote IDs, public pricing, email send or login password. Validating alone does not consume invitation use.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json).
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Mobile (390px)

Golden arch light echoes only at top; indigo content preserves contrast. Same serif and sans hierarchy as desktop. No admin hamburger. Body text fits the 65-character maximum line length and the mobile width.

Required content: Invitation Home Cinema, Your invitation is ready, Movies / Shows, Continue.

## Invitation states

Each is its own state of this route.

- Expired: 'Invitation expired. Ask the owner for a new link.'
- Used up: 'Invitation used up. All available places have been claimed.'

Expiry and use cap distinct. Public error contains no internal URL or ID. No stack trace. Gold action, lavender info, rose error, disabled button unambiguous.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then check desktop and mobile and audit the required states.
