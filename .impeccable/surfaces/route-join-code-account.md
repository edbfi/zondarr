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

Account authorization: the left screen of a two-screen board whose right screen is the access receipt (`route:/join/[code]/complete`). Generous whitespace, muted lavender information blocks.

## Visual reference

[Detailed mockup](../../docs/design/screens/03-account-and-access-summary.webp), left view.

Use the shared [design system](../../DESIGN.md). Match hierarchy, density and palette while building real semantic components. This is a screen composition; any side-by-side stages are separate routes or states.

## Required content

'Use your Plex account.' 'Continue with Plex'. Waiting state 'Waiting for Plex sign-in…' and Cancel.

## Acceptance criteria

No Zondarr account/password for Plex. Never expose remote IDs or internal addresses.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json); do not infer calculations from raster text.
- Apply the raster corrections below.
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Account states

[States and components board](../../docs/design/screens/10-recovery-and-components.webp), separate specimens; each is its own state of this route, not one screen.

- Server unavailable: 'Home Cinema is unreachable.' Retry.
- Account field validation: Jellyfin username field error 'Use lowercase letters, numbers or underscores.'

Public error contains no internal URL or ID. No stack trace. Gold action, lavender info, rose error, disabled button unambiguous.

## Raster corrections

Use the images for composition and visual character. Use DESIGN.md, PRODUCT.md, this brief's acceptance criteria and the demo fixtures for exact values and behavior. Body copy, chart axes, tiny icons and font glyphs remain illustrative raster renderings. Rebuild them as native accessible UI and verify them against the specification. A PNG cannot verify focus order, screen-reader announcements, permission checks or real responsiveness.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the attached detailed image as a composition reference and the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then compare desktop/mobile screenshots and audit the required states. Do not add incidental actions visible only in the raster.
