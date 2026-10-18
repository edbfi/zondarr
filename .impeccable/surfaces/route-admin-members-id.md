---
version: 1
slug: "route-admin-members-id"
primary_target: "route:/admin/members/[id]"
related_targets: ["route:/admin/members/alex","route:/admin/members"]
---

# Zondarr Member details and library access

## Status

Proposed design seed for review. Mode: **operate**. Audience: **Admin**. Proposed route: `/admin/members/alex`.

## Purpose and composition

Member list left, selected account details and library permissions right, connection health strip beneath. Flat plum panels and readable compact rows.

## Visual reference

[Detailed mockup](../../docs/design/screens/06-members-and-servers.webp)

Use the shared [design system](../../DESIGN.md). Match hierarchy, density and palette while building real semantic components. This is a screen composition; any side-by-side stages are separate routes or states.

## Required content

'Members'. Alex Plex Shared Active, Jordan Jellyfin Active, Morgan Plex Home Active. Alex Libraries Movies and Shows, joined 12 Oct 2025, access No expiry. Labelled permissions Stream, Transcode, Download (off). 'Sync members'. Footer connection Home Cinema Healthy / last sync 2 min ago.

## Acceptance criteria

No claimed auto removal. Show relationship types with text, not color only. Member permissions loaded values, no default all-on assumption.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json); do not infer calculations from raster text.
- Apply the raster corrections below.
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Raster corrections

Use the images for composition and visual character. Use DESIGN.md, PRODUCT.md, this brief's acceptance criteria and the demo fixtures for exact values and behavior. Body copy, chart axes, tiny icons and font glyphs remain illustrative raster renderings. Rebuild them as native accessible UI and verify them against the specification. A PNG cannot verify focus order, screen-reader announcements, permission checks or real responsiveness.

- Save permissions from loaded provider state. Do not infer streaming/download defaults from the decorative switch positions.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the attached detailed image as a composition reference and the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then compare desktop/mobile screenshots and audit the required states. Do not add incidental actions visible only in the raster.
