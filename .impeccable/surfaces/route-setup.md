---
version: 1
slug: "route-setup"
primary_target: "route:/setup"
related_targets: []
---

# Zondarr First-run claim

## Status

Proposed brief for `setup` ([docs/SPEC-setup.md](../../docs/SPEC-setup.md)), with no mockup. Mode: **operate**. Audience: **the person installing Zondarr**, who can read the server console or the container's logs. Route: `/setup`. It is ported from obzorarr's claim page (its `route-setup.md`), the reference for `setup`, and drawn in Zondarr's own design.

## Purpose and composition

One quiet, centred form within the 672px form width: the first screen a fresh install shows, before anyone is signed in. No admin navigation; the header has only the Zondarr logo (`static/zondarr-logo.svg`) and wordmark and the language switcher (`LanguageSwitcher.svelte`). Operational, not expressive: the admin side of Golden Welcome × Velvet Premiere, flat and practical, Outfit headings, no serif display and no arched light or imagery.

## Visual reference

None yet. Use the shared [design system](../../DESIGN.md): `background` page, one flat `surface` panel with a 1px `border` and the `panel` radius, `h1` heading, labelled `text-field` controls on `control-border`, helper text in `muted`, one solid `primary` button, `danger` text for errors, the `secondary` focus ring.

## Required content

Heading 'Claim this Zondarr'. One line: 'Enter the setup token from the server's output, then create the owner account.' Fields: 'Setup token' (helper: 'Shown as xxxx-xxxx-xxxx in the container's logs, or in the console when Zondarr runs directly. A new one is printed every 15 minutes.'), 'Username', 'Password' (helper: 'At least 15 characters.', with a Show/Hide control that shows what was typed). Primary action 'Claim and create owner'. While submitting: 'Claiming…', and the button can't be pressed twice. The numbers in the copy come from the constants the logic uses.

## Acceptance criteria

- Errors sit beside their field with helper/error IDs and `aria-invalid`; a wrong or expired token gets one message that names the server's output, never which of the two it was.
- After a failed submit, the username is kept; the token and password are not, and focus goes to the first field in error.
- The token field takes the token with or without dashes and in any case, and is set in IBM Plex Mono like the console line it came from; it is not a password field, so the person can check what they typed. Dashes are inserted as the token is typed, and without JavaScript it still takes any form.
- The Show/Hide control is a labelled button with a 20px line eye icon at the end of the password field; it appears only once the page has script, and the form works without it.
- No server, member, Plex or Jellyfin detail appears, and no address the server guessed.
- Test keyboard focus, visible labels, disabled behavior and 200% zoom; target 360, 390, 768 and 1440px viewports, in English and Danish. Translated text wraps without hiding the primary action, and at 360px the button is above the fold.
- Read reduced-motion preference before animating; the 100ms press feedback is the only motion.
- States: initial, field errors, token refused, submitting, the claim failing on the server. After success the browser leaves the page.

## Handoff prompt

> Implement only this surface in Zondarr's existing application. Read PRODUCT.md, DESIGN.md, docs/SPEC-setup.md and this brief first. Reuse existing Panda CSS tokens; build native accessible form controls. Keep it quiet: this is an operational screen.
