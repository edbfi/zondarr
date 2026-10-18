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

Final access receipt: the right screen of a two-screen board whose left screen is account authorization (`route:/join/[code]/account`). Serif success headline, generous whitespace, muted lavender information blocks.

## Visual reference

[Detailed mockup](../../docs/design/screens/03-account-and-access-summary.webp), right view.

Use the shared [design system](../../DESIGN.md). Match hierarchy, density and palette while building real semantic components. This is a screen composition; any side-by-side stages are separate routes or states.

## Required content

'You’re in.' Home Cinema / Movies / Shows / Plex access ready. 'Open Plex'. 'Next: install a Plex player on your TV, tablet or phone.'

## Acceptance criteria

Receipt is end of join flow, not persistent dashboard. Never expose remote IDs or internal addresses.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json); do not infer calculations from raster text.
- Apply the raster corrections below.
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Mobile (390px)

[Mobile board](../../docs/design/screens/09-mobile-invitee.webp), right view.

Three 390px mobile web screens share one board: invitation, house rules and success. No phone hardware. Golden arch light echoes only at top; indigo content preserves contrast. Same serif and sans hierarchy as desktop. No admin hamburger. Body text fits the 65-character maximum line length and the mobile width.

Required content: Success You’re in, Open Plex, allowed libraries.

## Raster corrections

Use the images for composition and visual character. Use DESIGN.md, PRODUCT.md, this brief's acceptance criteria and the demo fixtures for exact values and behavior. Body copy, chart axes, tiny icons and font glyphs remain illustrative raster renderings. Rebuild them as native accessible UI and verify them against the specification. A PNG cannot verify focus order, screen-reader announcements, permission checks or real responsiveness.

- No persistent invitee account dashboard is introduced. Access summary is the redemption success receipt.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the attached detailed image as a composition reference and the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then compare desktop/mobile screenshots and audit the required states. Do not add incidental actions visible only in the raster.
