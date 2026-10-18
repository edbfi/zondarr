---
version: 1
slug: "route-admin-settings"
primary_target: "route:/admin/settings"
related_targets: []
---

# Zondarr Server and account settings

## Status

Proposed design seed for review. Mode: **operate**. Audience: **Admin**. Proposed route: `/admin/settings`.

## Purpose and composition

Settings tabs General / Servers / Account / Sync / About. Main server connection form and separate account-security section, no decorative art.

## Visual reference

[Detailed mockup](../../docs/design/screens/08-settings-server-account.webp)

Use the shared [design system](../../DESIGN.md). Match hierarchy, density and palette while building real semantic components. This is a screen composition; any side-by-side stages are separate routes or states.

## Required content

'Settings'. Home Cinema connection, https://plex.example (admin only), stored API key •••• 4821, New key blank, Test connection, Save server. Sync every 15 minutes; 'Save sync schedule'. Account password, Two-factor enabled, Manage backup codes. Locked public address https://join.example, 'Managed by deployment'.

## Acceptance criteria

Source lacks server editing; this screen is an explicit proposed rewrite improvement with re-test requirement, captured in handoff notes. Never expose admin settings to invitees.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json); do not infer calculations from raster text.
- Apply the raster corrections below.
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Raster corrections

Use the images for composition and visual character. Use DESIGN.md, PRODUCT.md, this brief's acceptance criteria and the demo fixtures for exact values and behavior. Body copy, chart axes, tiny icons and font glyphs remain illustrative raster renderings. Rebuild them as native accessible UI and verify them against the specification. A PNG cannot verify focus order, screen-reader announcements, permission checks or real responsiveness.

- Server editing with a successful re-test is a proposed rewrite improvement, not existing shipped behavior. Reuse the edit form only after the implementation supports it.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the attached detailed image as a composition reference and the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then compare desktop/mobile screenshots and audit the required states. Do not add incidental actions visible only in the raster.
