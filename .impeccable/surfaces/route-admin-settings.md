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

None yet. Use the shared [design system](../../DESIGN.md).

## Required content

'Settings'. Home Cinema connection, https://plex.example (admin only), stored API key •••• 4821, New key blank, Test connection, Save server. Sync every 15 minutes; 'Save sync schedule'. Account password, Two-factor enabled, Manage backup codes. Public address read-only: when `ORIGIN` is set, its value with lock label 'Managed by deployment'; otherwise 'Not set: links use the address you're on'. Public invite address: optional; editable, or read-only with 'Managed by deployment' when the environment sets it; when empty, invite links use the address you're on or `ORIGIN`.

## Acceptance criteria

Server editing is new in the rewrite (the legacy app had none): a change saves only after a successful re-test. Never expose admin settings to invitees. `ORIGIN` is optional and never a stored setting, so the public address is never editable and its lock label shows only when `ORIGIN` is set. Don't caption the public address as the public link for invitees: that is the separate public invite address, which only builds invite links.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json).
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then check desktop and mobile and audit the required states.
