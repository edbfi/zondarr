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

[Detailed mockup](../../docs/design/screens/02-invitee-wizard.webp)

Use the shared [design system](../../DESIGN.md). Match hierarchy, density and palette while building real semantic components. This is a screen composition; any side-by-side stages are separate routes or states.

## Required content

Home Cinema. '2 / 3', thin gold progress. 'A few house rules.' Three concise rules Respect other members; Keep your account private; Use the library for personal viewing. Required unchecked checkbox 'I agree to the house rules.' Continue button disabled until agreed. Back link.

## Acceptance criteria

Unchecked required checkbox means Continue visibly disabled. No admin chrome. Wizard gold distinct from error colors; no auto-advance before required interaction.

- Preserve audience boundaries from [product context](../../PRODUCT.md).
- Use canonical data in [demo fixtures](../../tests/fixtures/demo-fixtures.json); do not infer calculations from raster text.
- Apply the raster corrections below.
- Make loading, empty, failure, pending and saved states available where the workflow needs them.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports.
- Read reduced-motion preference before animating. Long names and translated text must wrap without hiding the primary action.

## Mobile (390px)

[Mobile board](../../docs/design/screens/09-mobile-invitee.webp), middle view.

Three 390px mobile web screens share one board: invitation, house rules and success. No phone hardware. Golden arch light echoes only at top; indigo content preserves contrast. Same serif and sans hierarchy as desktop. No admin hamburger. Body text fits the 65-character maximum line length and the mobile width.

Required content: Rules 2/3, A few house rules, checked I agree to the house rules, Continue enabled. The required checkbox is checked only in this mobile screenshot state.

## Required terms state

[States and components board](../../docs/design/screens/10-recovery-and-components.webp), required-terms specimen: terms checkbox unchecked and Continue disabled. The disabled button is unambiguous.

## Raster corrections

Use the images for composition and visual character. Use DESIGN.md, PRODUCT.md, this brief's acceptance criteria and the demo fixtures for exact values and behavior. Body copy, chart axes, tiny icons and font glyphs remain illustrative raster renderings. Rebuild them as native accessible UI and verify them against the specification. A PNG cannot verify focus order, screen-reader announcements, permission checks or real responsiveness.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md and this brief first. Use the attached detailed image as a composition reference and the named tokens as exact values. Preserve Golden Welcome × Velvet Premiere. Keep the server's domain decisions authoritative. Reuse existing Panda CSS tokens and Ark UI primitives. Build native accessible controls, then compare desktop/mobile screenshots and audit the required states. Do not add incidental actions visible only in the raster.
