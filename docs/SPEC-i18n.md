# Spec: `i18n`

**Status:** built (2026-11-08), module 2 of the capability map ([docs/SPEC.md](SPEC.md)); D21 and
D22 hold the decisions. obzorarr is the reference app for `i18n`
([Shared groundwork](../AGENTS.md#shared-groundwork)): this spec ported obzorarr's, with the
message-check rules its #301 added, and its code and tests at `7368cff`. This file keeps what the
code and tests can't say. The full text before this cut is `50a41c0:docs/SPEC-i18n.md`. **What
differs from obzorarr:**
- the placeholder's English and Danish text (`src/routes/(public)/+page.svelte`), and the name
  Zondarr instead of Obzorarr;
- where the switcher shows: the placeholder `/` only, since zondarr has no landing page; the admin
  shell (`sign-in`) and the join shell (`join`) place it when they are built (below);
- which zone callers pass to `formatDateTime`: zondarr has no instance zone, so obzorarr's
  instance-zone rule (its D24) doesn't carry over (below);
- not translated through the messages: zondarr's wizard steps, which `wizards` translates per step
  (D21); the wizard's own content-language switch is separate from the switcher;
- no English spelling rule, since zondarr's D21 sets none;
- the decision numbers: D21, D22, D16 (runtime validation gaps) and D26 (dependencies).

Everything else is the same as obzorarr's, the cookie name included, so a language chosen in one
edbfi app carries over to the others on the same host. The global `:focus-visible` rule, which
obzorarr left to each app's first focusable control, is the same rule as obzorarr's and landed with
the switcher, zondarr's first focusable control.

## Objective

Every later module writes its user-facing text as messages in English and Danish, compiled by
Paraglide JS into typed message functions, and shows numbers and dates formatted for the viewer's
language (D21, D22). Each request uses the viewer's choice, then the browser's preferred languages,
then English, and the browser keeps the language the server chose for the page.

The one-off validations D22 asked for (the pinned versions with no Node on `PATH`, the Weblate round
trip, the adapter-bun build and the concurrency check) passed in zondarr's own runs. Their scripts
and output are in the bodies of #342 and #343, and #344 lists each with its evidence.

## Versions

`@inlang/paraglide-js` 3 and `@inlang/plugin-i18next` 6, exact-pinned dev dependencies. The owner
approved both packages for every edbfi app on 2026-10-29, and Paraglide JS 3 on 2026-11-06 (D22).
TypeScript stays on 6.x (D2): Paraglide 3 writes its declarations itself and needs no TypeScript.

## Messages

**The files** are i18next JSON v4 (D22): one flat object per language, formatted by Biome like the
rest of the repo. Every language the project has has exactly one file, and there is no file for
another language, which Paraglide would ignore without a word.

**Message names** are snake_case, starting with the module or surface that owns them
(`placeholder_title`, `error_not_found_title`). So each is a JavaScript name,
`m.placeholder_title()`, and Paraglide's escaped names and the `m["a.b"]()` form of nested keys
never appear.
- **Plural forms:** a key that ends in a CLDR plural category (`_zero`, `_one`, `_two`, `_few`,
  `_many`, `_other`) is a plural form of the message named by the rest of the key
  (`invitation_uses_one` belongs to `invitation_uses`), whether or not it was meant as one, so the
  plural rules below apply to it. A message is either one key or plural forms, never both.
- **`_ordinal`:** no key contains `_ordinal_`, which the plugin reads as an ordinal plural.
- **Renaming:** once Weblate is connected, keys aren't renamed, because translations are tied to
  them.

**Placeholders** are `{{name}}`.
- A count or quantity is written `{{name, number}}`, which Paraglide formats with
  `Intl.NumberFormat` in the message's language ("1,234 members", "1.234 medlemmer"). A bare
  `{{count}}` would print "1234".
- A number that is a name rather than a quantity, such as a year, is a bare `{{year}}`: the
  `number` format would print "2,025".
- No format other than `number` is allowed, compared as the whole text after the first comma: the
  plugin would silently keep only `number` from `{{name, number, compact}}`. In particular,
  Paraglide compiles `{{name, datetime}}` to `Intl.DateTimeFormat` with no time zone, which formats
  in the zone of whatever machine runs it. Dates are formatted with `formatDateTime` (below) and
  passed in as text.
- A number in a message that states how the app behaves (a limit, a duration, a count) is passed in
  from the constant the logic uses, never written into the text, so the copy can't drift from the
  behaviour.

**Plurals** are `<name>_one` and `<name>_other`, chosen by `count`. English and Danish both have
exactly these two categories (`Intl.PluralRules`). Danish uses `one` for every number below 2 except
0 (0.5 and 1.5 included), so every plural form keeps `{{count, number}}`, under exactly that name,
rather than writing the number out ("1 dag" would misstate 1.5 days).

**Messages are plain text.** They are rendered as text, never with `{@html}`, so a placeholder
filled with a name can't inject markup.
- **No tags:** the plugin reads anything shaped like a tag (`<address>`, `<br/>`, `</b>`, `<0>`) as
  markup, and Paraglide drops it from the text without a warning: `ORIGIN=<address>` renders as
  `ORIGIN=`. A value to fill in is a placeholder (`ORIGIN={{address}}`). The check reports what the
  plugin reads as markup, and also any tag with a `name=` attribute anywhere in it, spaces around
  the `=` included (`<a href="/help">`, `<input disabled name="x">`): the plugin keeps those as
  text, but they are HTML that would show to the viewer as raw tags. Plain angle brackets in prose
  (`1 < 2 and 3 > 2`, `<5 minutes (>1 play)`, `a<b and c>d`) pass, and so does a tag with only bare
  attributes (`<input disabled>`), which has the same shape as that prose.
- **Markup inside a message,** such as a link in a sentence, is left to the first module that needs
  it.

**Not translated through the messages:**
- the name Zondarr: on its own, as in the page's `<title>`, it isn't a message, and inside a
  message it stays "Zondarr" in both languages ("Zondarr is being rebuilt.");
- text the owner writes (D21), such as server names and the wizards' steps, which `wizards`
  translates per step with its own content-language switch (SPEC.md's Module notes).
  That switch chooses a step's content language and is separate from the language switcher, which
  chooses the interface's. Whether the defaults `wizards` pre-fills for an interaction ("I
  understand") are messages or content is `wizards`' to decide;
- log entries and console output, which are for operators and stay in English;
- the switcher's language names (below).

**Who writes them:** agents write the English and the Danish. The owner may spot-check the Danish
but doesn't approve it, and Weblate corrects it later. D21 sets no English spelling, so this spec
adds no spelling rule, and the copy follows PRODUCT.md's copy rules.

**The message check,** `src/lib/shared/i18n/messages.test.ts`, holds the check and its tests. It
sits in `src/` only because Vitest runs `src/**`, so it runs in prek's `tests` hook and in CI. It
finds every problem in `messages/*.json` against the rules above: one file for each of the
project's languages and no other; flat, non-empty string values; names, `_ordinal_` and one key or
plural forms; the same messages in every language; the same placeholders, names and formats in
every form; `number` as the only format; exactly the plural forms `Intl.PluralRules` gives each
language, each with `{{count, number}}`; and no tags.

## The toolchain

`project.inlang/settings.json` holds the locales and the i18next plugin, and
`project.inlang/paraglide.config.ts` holds Paraglide's options, which the CLI and the Vite plugin
both read.
- **The plugin loads from `node_modules`,** so nothing is fetched at build time or in CI.
- `"contextValues": []` turns off the plugin's guess at i18next contexts, which would read a key
  such as `title_short` next to `title` as a variant of `title`.
- `outputStructure: "message-modules"` is set because the CLI and the Vite plugin would otherwise
  write different layouts into the same folder: the Vite plugin's default (`virtual-modules`) is one
  the CLI can't write. Running `check` beside `dev` would then rewrite the folder under the dev
  server.
- `project.inlang/cache/` is gitignored because Paraglide 3 writes no `.gitignore` of its own there,
  and without the line `lint` fails on the cache files.

**The compiled output** (`src/lib/paraglide/`, gitignored):
- **`#lib/paraglide/messages.js` and `#lib/paraglide/runtime.js`** are browser-safe.
- **`#lib/paraglide/server.js`,** the middleware, loads `async_hooks` for AsyncLocalStorage. In app
  code only `src/hooks.server.ts` imports it.
- **The import rules:** the output is generated code that imports nothing from the app. It isn't one
  of the app's layers, so `lib/shared/`, components, services and routes import it as they import
  `#styled-system`.

## Choosing the language

**On the server,** `handle` in `src/hooks.server.ts` runs every request through
`paraglideMiddleware`:
- **The order:** the `PARAGLIDE_LOCALE` cookie when it holds `en` or `da`; any other value is
  ignored. Then the best match in `Accept-Language` (`da-DK` gives `da`). Then English. There are no
  URL prefixes.
- **The request:** the middleware's copy of the request is passed on a copy of the event, because
  `event.request` is read-only in SvelteKit 3. The event is a plain object, so the copy keeps every
  field, and form actions read their body from it.
- **`<html lang>`:** `transformPageChunk` writes the language into `src/app.html`'s
  `<html lang="%lang%" class="dark">`. The Biome suppression comment just above it must not contain
  the `%lang%` token itself: `replace` swaps only the first occurrence, so the token in the comment
  would be filled in and the attribute left as it was.
- **Caching:** the middleware adds `Vary: Cookie, Accept-Language` to every response. No page is
  prerendered, since a prerendered page would have one language for everyone.
- **First in `handle`:** the language handle refuses nothing and never reads the body. Later modules
  add their stages after it with `sequence`. Errors thrown while rendering a route reach
  `+error.svelte` in the viewer's language.

**A later stage that refuses a request returns its response; it never throws.** An error thrown out
of a `handle` stage, `error(403)` included, leaves the middleware. SvelteKit then renders its
fallback page in English, without `<html lang>` or `Vary`.
A response returned from inside the chain is still in the request's language and gets `Vary`, but it
skips `transformPageChunk`, so a refusal page that a stage builds sets its own `<html lang>`. This
binds `setup`'s gate and `sign-in`'s refusals.

**In the browser,** `src/hooks.client.ts` reads the page's `<html lang>` once, when the app starts,
and makes Paraglide's `getLocale()` return it, or English if it isn't `en` or `da`. The server's
choice holds for the whole page, until it reloads. It is read once because a browser's page
translation can rewrite `<html lang>` later.
- **Why:** without the hook, Paraglide's browser runtime would choose again from
  `navigator.languages`, which needn't match the `Accept-Language` header the server saw.
- **The unasked cookie:** on its first call, the runtime would also store whatever it chose in the
  cookie. The browser's language would become a stored choice the viewer never made, and a later
  change of browser language would no longer count (D21's order).

**An accepted limit:** a tab keeps its language until it reloads. If the viewer switches language in
another tab, text that a server `load` or action returns to the first tab follows the new cookie
until that tab reloads.

## The language switcher

`src/lib/components/layout/LanguageSwitcher.svelte` is a labelled group of native buttons, one per
language, styled only with tokens. The group's label is a message. The owner chose buttons over a
`<select>` for obzorarr (2026-11-06), and the reason holds here: in Chrome and Edge on Windows and
Linux, an arrow key on a closed `<select>` fires `change`, so a keyboard user looking at the options
would be switched and lose focus (WCAG 2.2, 3.2.2 On Input).
- **The names:** each button names its language in that language ("English", "Dansk"), from
  `Intl.DisplayNames`. They are the same in every language, so they aren't messages, and a viewer
  who can't read the current language still finds their own.
- **Pressing another language** calls Paraglide's `setLocale`, which writes `PARAGLIDE_LOCALE` and
  reloads the page in the new language. The cookie has path `/`, lasts about 400 days (Paraglide's
  default) and is `SameSite=Lax`. It is `Secure` exactly when the page is on `https`
  (`cookieSecure: "auto"`), as `sign-in`'s cookie rule asks.
- **Who writes the cookie:** only the browser, so it is readable by scripts, and it holds only a
  language. The server only reads it.
- **Sharing the cookie:** it keeps Paraglide's default name. Cookies ignore ports, so every app on
  the same host shares it. A choice made in one edbfi app carries over to the others there. A value
  another app wrote that isn't `en` or `da` is ignored.
- **Without JavaScript** the switcher does nothing, and the browser's preferred languages still
  apply.
- **Keyboard focus** is one global rule in Panda's `globalCss` (SPEC.md's Design tokens): a
  per-component outline would need a 2px offset that no spacing token has (`strictTokens` refuses
  it), and one rule keeps the ring the same on every later control.
- **Where it shows:** on the placeholder `/`, above the heading. zondarr has no landing page and no
  brief for `/`, so no brief gained it in this module. Each shell places it when that shell is
  built, and its module's spec updates the shell's briefs: the admin shell (`sign-in`) and the
  public join shell (`join`, the `route-join-code*.md` briefs), where it stays apart from the
  wizard's content-language switch. It needs no brief of its own.

## Formatting

`src/lib/shared/i18n/format.ts` is browser-safe and formats in the current language
(`getLocale()`), on the server and in the browser alike. The language picks the `Intl` locale, not
the browser's region, so server and browser always agree: `da` formats as `da`, and `en` as `en-GB`
(the owner's choice, 2026-11-06, for every edbfi app), with the day first and a 24-hour clock
("05/11/2026, 23:30"). A message's `{{name, number}}` formats as `en`, which groups numbers the same
way.
- `formatNumber(value, options?)`: `Intl.NumberFormat`.
- `formatDateTime(value, options & { timeZone: string })`: `Intl.DateTimeFormat`.
  - **The zone is required,** so nothing is formatted in the server's or the browser's own zone,
    which differ from each other and give a server-rendered page and its hydrated copy different
    text.
  - **Which zone:** zondarr has no instance zone, and every caller passes a zone explicitly.
    Callers pass `"UTC"` for a calendar value, such as a month's name or a date with no time of day.
    The zone a point in time is shown in (a sync run, a log entry) is decided in the spec of the
    first module that shows one; if that needs a setting, that module asks the owner. That records
    are stored in UTC (`setup`'s Module notes) doesn't decide how they are shown.

Counts and quantities inside a message use `{{name, number}}` instead. Other formatters (relative
times, lists) come with the first module that needs one.

## Weblate

Connecting Weblate is later work (D21). The round trip in #342 fixed what the component needs:
- format `i18nextv4`, monolingual;
- file mask `messages/*.json`, with `messages/en.json` as the base file;
- file format parameters `json_indent: 1` and `json_indent_style: tabs`, with keys left unsorted,
  so its commits pass Biome.

## Boundaries

- **Always:** every user-facing string as a message in both languages (titles, labels, alt text and
  accessible names included); counts and quantities in messages as `{{name, number}}`; dates through
  `formatDateTime` with an explicit zone; messages rendered as text; refusals in `handle` returned,
  never thrown.
- **Ask first:** another language; another message format or Paraglide's URL strategy; markup inside
  messages; any dependency beyond the two packages.
- **Never:** text written into a component or service; `{{name, datetime}}` or a tag in a message;
  a prerendered page with translated text; the server writing the language cookie; connecting
  Weblate in this module.
