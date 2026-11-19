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

None yet. Use the shared [design system](../../DESIGN.md).

## Required content

'Community overview'. 48 members, 6 active invitations, 2 connected servers. 'Create invitation'. Servers Home Cinema Plex Healthy, Living Room Jellyfin Healthy. Recent activity Alex joined / Invitation MOVIENIGHT created / Libraries synced. Pending invitations with use count and expiry.

## Acceptance criteria

Admin perspective distinct from invitee screens. No playback stats or emails sent. No serif large hero inside operational dashboard. Pending-invitation rows (codes, counts, dates and statuses) come from the fixture and the server; a capped active invitation with three or fewer remaining uses is Limited, so MOVIENIGHT at 2/5 is Limited, not Active.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json).
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then check desktop and mobile and audit the required states.
