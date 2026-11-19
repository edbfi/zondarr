---
version: 1
slug: "route-admin-wizards-id"
primary_target: "route:/admin/wizards/[id]"
related_targets: ["route:/admin/wizards/house-rules"]
---

# Zondarr Wizard builder and preview

## Status

Proposed design seed for review. Mode: **operate**. Audience: **Admin**. Proposed route: `/admin/wizards/house-rules`.

## Purpose and composition

Three panes: ordered steps, actual content editor and cinematic gold/indigo public preview. Outfit editor UI; DM Serif Display preview headings.

## Visual reference

None yet. Use the shared [design system](../../DESIGN.md).

## Required content

'Welcome wizard'. Steps Welcome / House rules / Set up your player; Move up / Move down buttons. Title A few house rules. Language English. Content field. Required terms module enabled. Preview 2/3, unchecked I agree to the house rules, Continue disabled. 'Save wizard', 'Preview as invitee'.

## Acceptance criteria

Editor and preview must show same content. Keyboard reorder controls. Preview labelled so admin knows this is invitee view. No answers exposed in quizzes.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json).
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then check desktop and mobile and audit the required states.
