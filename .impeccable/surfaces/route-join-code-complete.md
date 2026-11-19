---
version: 1
slug: "route-join-code-complete"
primary_target: "route:/join/[code]/complete"
related_targets: ["route:/join/MOVIENIGHT/complete"]
---

# Zondarr Access summary

## Status

Proposed design seed for review. Mode: **operate**. Audience: **Invitee**. Proposed route: `/join/MOVIENIGHT/complete`.

## Purpose and composition

Final access receipt, after account authorization (`route:/join/[code]/account`). Serif success headline, generous whitespace, muted lavender information blocks.

## Visual reference

None yet. Use the shared [design system](../../DESIGN.md).

## Required content

'You’re in.' Home Cinema / Movies / Shows / Plex access ready. 'Open Plex'. 'Next: install a Plex player on your TV, tablet or phone.'

## Acceptance criteria

The access summary is the redemption success receipt and the end of the join flow; no persistent invitee account dashboard is introduced. Never expose remote IDs or internal addresses.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json).
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Mobile (390px)

Golden arch light echoes only at top; indigo content preserves contrast. Same serif and sans hierarchy as desktop. No admin hamburger. Body text fits the 65-character maximum line length and the mobile width.

Required content: Success You’re in, Open Plex, allowed libraries.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then check desktop and mobile and audit the required states.
