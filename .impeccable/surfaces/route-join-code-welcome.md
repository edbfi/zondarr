---
version: 1
slug: "route-join-code-welcome"
primary_target: "route:/join/[code]/welcome"
related_targets: ["route:/join/MOVIENIGHT/welcome"]
---

# Zondarr House rules and required interaction

## Status

Proposed design seed for review. Mode: **experience**. Audience: **Invitee**. Proposed route: `/join/MOVIENIGHT/welcome`.

## Purpose and composition

Centred 680px onboarding column, indigo vignette and subtle gold arch at edge, huge restrained serif title; content readable with quiet step counter.

## Visual reference

None yet. Use the shared [design system](../../DESIGN.md).

## Required content

Home Cinema. '2 / 3', thin gold progress. 'A few house rules.' Three concise rules Respect other members; Keep your account private; Use the library for personal viewing. Required unchecked checkbox 'I agree to the house rules.' Continue button disabled until agreed. Back link.

## Acceptance criteria

Unchecked required checkbox means Continue visibly disabled. No admin chrome. Wizard gold distinct from error colors; no auto-advance before required interaction.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json).
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Mobile (390px)

Golden arch light echoes only at top; indigo content preserves contrast. Same serif and sans hierarchy as desktop. No admin hamburger. Body text fits the 65-character maximum line length and the mobile width.

Required content: Rules 2/3, A few house rules, I agree to the house rules, Continue, enabled once the box is checked.

## Required terms state

Terms checkbox unchecked and Continue disabled. The disabled button is unambiguous.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then check desktop and mobile and audit the required states.
