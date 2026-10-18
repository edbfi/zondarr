---
version: 1
slug: "route-admin"
primary_target: "route:/admin"
related_targets: []
---

# Zondarr Admin community overview

## Status

Proposed design seed for review. Mode: **operate**. Audience: **Admin**. Proposed route: `/admin`.

## Purpose and composition

Practical velvet-indigo admin shell, Outfit headings, muted gold primary actions, compact overview metrics and activity list. No photography behind data.

## Visual reference

[Detailed mockup](../../docs/design/screens/04-admin-dashboard.webp)

Use the shared [design system](../../DESIGN.md). Match hierarchy, density and palette while building real semantic components. This is a screen composition; any side-by-side stages are separate routes or states.

## Required content

'Community overview'. 48 members, 6 active invitations, 2 connected servers. 'Create invitation'. Servers Home Cinema Plex Healthy, Living Room Jellyfin Healthy. Recent activity Alex joined / Invitation MOVIENIGHT created / Libraries synced. Pending invitations with use count and expiry.

## Acceptance criteria

Admin perspective distinct from invitee screens. No playback stats, emails sent or enforced-expiry claims. No serif large hero inside operational dashboard.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json); do not infer calculations from raster text.
- Apply the raster corrections below.
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Raster corrections

Use the images for composition and visual character. Use DESIGN.md, PRODUCT.md, this brief's acceptance criteria and the demo fixtures for exact values and behavior. Body copy, chart axes, tiny icons and font glyphs remain illustrative raster renderings. Rebuild them as native accessible UI and verify them against the specification. A PNG cannot verify focus order, screen-reader announcements, permission checks or real responsiveness.

- The pending-invitations rows (codes, counts, dates and statuses) are illustrative; take them from the fixture and the server. A capped active invitation with three or fewer remaining uses is Limited, so MOVIENIGHT at 2/5 is Limited, not Active.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the attached detailed image as a composition reference and the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then compare desktop/mobile screenshots and audit the required states. Do not add incidental actions visible only in the raster.
