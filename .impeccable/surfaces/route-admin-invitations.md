---
version: 1
slug: "route-admin-invitations"
primary_target: "route:/admin/invitations"
related_targets: []
---

# Zondarr Invitation list and editor

## Status

Proposed design seed for review. Mode: **operate**. Audience: **Admin**. Proposed route: `/admin/invitations`.

## Purpose and composition

Dense invitation list and right creation drawer with grouped targets, restrictions and welcome-flow options. Gold selected codes, purple focus.

## Visual reference

[Detailed mockup](../../docs/design/screens/05-invitations-editor.webp)

Use the shared [design system](../../DESIGN.md). Match hierarchy, density and palette while building real semantic components. This is a screen composition; any side-by-side stages are separate routes or states.

## Required content

'Invitations'. MOVIENIGHT Limited 2/5; FAMILY Limited 1/3; WEEKEND Used up 5/5; SUMMER Expired 0/3. Drawer 'Create invitation': Servers Home Cinema selected; Libraries Movies / Shows; Maximum uses 5; Invitation expires 31 Dec 2025; Access duration No expiry; Welcome wizard House rules. 'Create invitation'.

## Acceptance criteria

Use codes letters/digits only. FAMILY has 2 remaining hence Limited. Distinguish invite expiry from member duration. No email send field; share via copy link. Canonical status MOVIENIGHT 2/5 is Limited because three uses remain; fixture is authoritative.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json); do not infer calculations from raster text.
- Apply the raster corrections below.
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Copy-link feedback

[States and components board](../../docs/design/screens/10-recovery-and-components.webp), copy-link specimen: admin toast 'Invitation link copied', with primary and secondary variants. Gold action, lavender info.

## Raster corrections

Use the images for composition and visual character. Use DESIGN.md, PRODUCT.md, this brief's acceptance criteria and the demo fixtures for exact values and behavior. Body copy, chart axes, tiny icons and font glyphs remain illustrative raster renderings. Rebuild them as native accessible UI and verify them against the specification. A PNG cannot verify focus order, screen-reader announcements, permission checks or real responsiveness.

- The admin dashboard uses Outfit headings; the invitation-list raster uses a serif title. Resolve operational headings to Outfit per DESIGN.md, reserving DM Serif Display for public welcome and preview surfaces.
- A capped active invitation with three or fewer remaining uses is Limited. MOVIENIGHT at 2/5 therefore has status Limited; use the fixture rather than the raster's Active label.
- The copy-link specimen's address (`https://zondarr.example/invite/7K3pQ9`) is illustrative. Copy the real join link for the code.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the attached detailed image as a composition reference and the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then compare desktop/mobile screenshots and audit the required states. Do not add incidental actions visible only in the raster.
