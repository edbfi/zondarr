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

None yet. Use the shared [design system](../../DESIGN.md).

## Required content

'Members'. Alex Plex Shared Active, Jordan Jellyfin Active, Morgan Plex Home Active. Alex Libraries Movies and Shows, joined 12 Oct 2025, access No expiry. Labelled permissions Stream, Transcode, Download (off). 'Sync members'. Footer connection Home Cinema Healthy / last sync 2 min ago.

## Acceptance criteria

No claimed auto removal. Show relationship types with text, not color only. Member permissions show and save the values loaded from the provider; never assume a default, all-on or otherwise.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json).
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then check desktop and mobile and audit the required states.
