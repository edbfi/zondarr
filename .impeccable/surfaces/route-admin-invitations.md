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

None yet. Use the shared [design system](../../DESIGN.md).

## Required content

'Invitations'. MOVIENIGHT Limited 2/5; FAMILY Limited 1/3; WEEKEND Used up 5/5; SUMMER Expired 0/3. Drawer 'Create invitation': Servers Home Cinema selected; Libraries Movies / Shows; Maximum uses 5; Invitation expires 31 Dec 2025; Access duration No expiry; Welcome wizard House rules. 'Create invitation'.

## Acceptance criteria

Use codes letters/digits only. A capped active invitation with three or fewer remaining uses is Limited, so MOVIENIGHT 2/5 and FAMILY 1/3 are Limited; the fixture is authoritative. Distinguish invite expiry from member duration. No email send field; share via copy link. The page title and other operational headings use Outfit; DM Serif Display is only for public welcome and preview surfaces (DESIGN.md).

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json).
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Copy-link feedback

Admin toast 'Invitation link copied', with primary and secondary variants. Copy link copies the code's real join link. Gold action, lavender info.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then check desktop and mobile and audit the required states.
