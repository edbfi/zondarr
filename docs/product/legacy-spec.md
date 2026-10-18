# Zondarr

> [!NOTE]
> **Legacy product specification**, imported from the pre-rewrite documentation. It describes the
> shipped app's behaviour, which the rewrite keeps unless an approved spec or decision changes it.
> Its technology and deployment content is superseded by [`docs/decisions.md`](../decisions.md) and
> [`docs/SPEC.md`](../SPEC.md): §2 (status of the old code), §9.1 (deployment shape), the store, port
> and cross-origin rows in §9.2, the developer launcher in §9.4, and the separate web layer that
> relays to a backend (§3.3, the relay hygiene in §10, the store and worker notes in §11). Its visual
> design (§3.1) is superseded by [PRODUCT.md](../../PRODUCT.md) and [DESIGN.md](../../DESIGN.md).
> Sections are deleted as approved `docs/SPEC-<id>.md` files cover them, and the file goes once
> nothing is left (AGENTS.md, cleanup procedures).

Unified invitation and user management for Plex and Jellyfin media servers.

The name comes from the Russian word for "probe" (зонд), fitting an application that continually probes the media servers it manages: it tests connections, auto-detects server types, checks reachability before letting someone join, and keeps polling servers to reconcile accounts and libraries.

## 1. Purpose

Zondarr solves one problem for people who run a private media server for friends and family: letting other people in without doing it by hand. Instead of the owner creating accounts one at a time, sending credentials, and later forgetting who was given access, the owner creates an **invitation code**, shares a link, and the invitee onboards themselves. The invitee can be walked through a configurable sequence of pages first (rules of the house, a terms-of-service checkbox, a short quiz, a forced reading pause) and only then gets an account.

It is for a single administrator or a small group of co-administrators who own one or more media servers. Invitees never sign in to Zondarr; their only contact with it is the public join page.

Where it sits in a self-hosted media stack: alongside the media server(s), as the "front door" for new members. It is a peer of tools such as Wizarr or Overseerr-style request managers, but its scope is strictly membership: who gets an account, on which servers, with which libraries, for how long, and after agreeing to what.

What it deliberately does **not** do:

- It does not manage media, requests, downloads, subtitles, playback or transcoding.
- It does not store or proxy media server passwords for members; it uses the server's own API token.
- It does not send email or notifications of any kind. The invite link is shared out of band.
- It does not enforce per-user permissions itself; permissions live on the media server and Zondarr only edits them.
- It does not act as an identity provider for the media servers; it creates accounts on them and records the link.
- It is not multi-tenant. One instance serves one owner's set of servers and one admin role.

## 2. Status

**Shipped and used in practice, never formally released.** The codebase reached feature-complete status within its first week (early February 2026), was then hardened for eight months with roughly three hundred reviewed pull requests, and was run by its author ("dogfooding" findings are recorded in the history). There are no versioned releases, no tags and no changelog; version numbers are placeholders, and the project README still carries a "work in progress" heading. The rewrite team should treat everything below as built and exercised unless this document explicitly marks it as a gap or an unvalidated design.

Two things were planned in the original design but never built: support for additional server platforms beyond Plex and Jellyfin (Emby and an audiobook server were named as examples), and automatic disabling or deletion of members whose access period has ended. Both are called out in section 12.

## 3. Product feel and goals

### 3.1 Intended experience

Two very different audiences see two very different surfaces, and the product is deliberate about keeping them apart.

**The admin console** is a dark "control room". The design language is near-black backgrounds, slightly lighter surface panels, fine neutral borders, and a single bright cyan accent for primary actions, active navigation and focus rings. Status is always encoded in three colours with fixed meaning: emerald for good or active, amber for attention (pending, limited, expiring soon, recovering), rose for problems (disabled, expired, used up, circuit open). Secondary tints are reserved for specific concepts: violet for servers, indigo/purple/teal for the three Plex relationship types, blue for informational items. A full light theme exists and follows the operating system by default, but dark is the brand look and the admin's toggle choice is remembered in the browser.

Typography reinforces the console feel: a clean humanist sans-serif for body copy, and a technical monospace for the wordmark, page titles, numbers, codes, identifiers, addresses, dates and log lines. Invitation codes appear as monospace chips in the accent colour. Detail pages use uppercase, letter-spaced micro-labels. Density is medium (cards with generous padding, compact tables, small muted helper text), with one deliberate exception: the log viewer is dense on purpose, with one-line rows in very small monospace text and virtualised scrolling so thousands of entries stay fast.

**The end-user wizard** (what an invitee sees while onboarding) is a separate "cinematic" experience. It is always dark regardless of theme, uses a gold accent instead of cyan, soft glows, a friendlier geometric sans-serif, a large "N / M" step counter with a thin gold progress bar, generous line length (about 65 characters) and a constrained content width. The intent, recorded in the history, is that onboarding should feel like a welcome, not like an admin form. Gold is reserved for wizard-related elements everywhere, including the interaction "modules" in the builder and the "preview mode" badge, so the admin always knows when they are looking at what the invitee will see.

**The join page shell** around the wizard is minimal: a sticky header with logo and wordmark, a theme toggle, and a wide centred column that moves through clearly named stages ("Validate your invitation code to get started", "Complete the required steps to continue", "Create your account", "Welcome aboard!").

### 3.2 Tone of voice

Plain, direct, second person. Short full sentences ending in a full stop ("You can change this later in Settings."). Every destructive confirmation says "This action cannot be undone." Progress labels end in an ellipsis ("Saving...", "Syncing Users..."). Em dashes separate a headline from its detail ("Connected — Plex server detected"). Empty states always pair a short title with a one-sentence explanation of how the list will fill ("No users yet" / "Users will appear here once they redeem invitation codes and create accounts on your media servers."). A rewrite should keep this voice but fix two inconsistencies: capitalisation drifts between Title Case and sentence case, and some technical terms leak into the admin UI unexplained (trusted origin, circuit breaker, external user ID, environment variable, the event-stream term on the logs page).

### 3.3 Opinionated choices and why

| Choice | Reasoning recorded in the history |
|---|---|
| Expiry is checked before "disabled" when validating a code | The background job disables expired invitations, so without this order invitees would see "disabled by the administrator" instead of the true reason. |
| A fully used invitation shows "Used up", never "Expired" | Dogfooding found the conflation confusing; the server decides activeness so that browser clock skew cannot mislabel a code. |
| Generated codes exclude the characters 0, O, I and L | Codes are read aloud and typed by hand; ambiguous glyphs cause support requests. |
| A media server cannot be added until a live connection test succeeds, and editing any field invalidates the test | "0 libraries detected" after adding a mistyped server was a recurring failure. |
| Server type is auto-detected from the address and key | Users should not need to know which product they are pointing at; Plex is the default guess. |
| Plex invitations require the invitee to sign in with Plex; the username is derived from their Plex email | Plex sharing is keyed to a Plex account; letting the invitee type a username produced orphaned invites. |
| Plex library sharing is direct, with no friend request to accept | A pending friend request the invitee must find and accept is the single biggest drop-off in a Plex onboarding. |
| The silent "fall back to a friend request" path was removed | A failed share must be visible, not quietly downgraded. |
| Account creation on a media server is attempted exactly once; only connecting is retried | A retried create can produce a duplicate or an orphan account that nothing knows how to clean up. |
| Redemption reserves a use before doing anything else | Concurrent redemptions must never exceed the use limit; the reservation is released if anything later fails. |
| Pre-registration wizard completion is proven with a signed token | Without it a client could skip the wizard and call the redemption step directly. |
| Quiz wrong answers trigger a growing cool-down (3 s, then 5, 7, 9, 10) and the correct answer is never sent to the browser | Quizzes exist to make people read; brute-forcing must be slow and the answer must be unguessable from the page. |
| The timer interaction completes itself and keeps real time across reloads, backgrounded tabs and locked screens | A "Continue" button after a timer was redundant, and reloading must not reset or shorten the wait. |
| The "Powered by Zondarr" footer was removed | The join page is the owner's front door, not the tool's advertisement. |
| Stale users (local but gone from the server) are reported, never deleted automatically | Sync must be safe to run unattended; destructive reconciliation is a human decision. |
| Existing server accounts are imported automatically on server add and on scheduled sync | The user list should reflect reality, including members who predate Zondarr. |
| Settings supplied by the operator's environment are shown as locked in the console | Container operators expect environment to win; the UI must not pretend otherwise. |
| The first admin can only be created with a one-time bootstrap token printed in the server log | An unauthenticated "create first admin" step on a reachable port is a takeover risk. |
| External (Plex/Jellyfin) sign-in never creates admins; it must be linked to an existing admin, and Plex sign-in must be the server owner | Auto-provisioning admins from a media account was a privilege-escalation path. |
| The whole browser surface is same-origin; the web layer relays to the backend | Home deployments must work without any cross-origin configuration. |
| Writes are refused in production until a trusted origin is configured | Deny by default; the setup wizard makes configuring it unavoidable. |

### 3.4 Goals stated at the outset

- Every endpoint except public join and validation requires authentication.
- User lists must remain usable with more than a thousand members (pagination, server-side search and filters).
- Synchronisation must be idempotent and tolerate partial failure.
- The interface should meet WCAG 2.1 AA.
- Adding another server platform should require only a new provider module that declares its own capabilities, so the UI never hard-codes Plex or Jellyfin behaviour.

## 4. Users, roles and permissions

| Role | Who | What they can do |
|---|---|---|
| Administrator | The server owner and anyone they create an admin account for | Everything in the console: servers, invitations, users, wizards, settings, logs, their own profile and two-factor settings, linking an external sign-in. |
| Invitee (public) | Anyone holding a valid invitation link | Validate a code, complete wizards, create an account or sign in with Plex, and see the success page. No sign-in to Zondarr ever exists for them. |
| Operator | Whoever deploys the instance | Sets environment-level configuration (secret, database, public origin, intervals, provider credentials), which locks the corresponding console settings. |

There is exactly one admin role with no per-admin permissions. Any admin can do anything, including creating more admins is **not** offered in the UI; after the first admin, further admins can only be created outside the product (there is no admin-management screen, which is noted as a gap). An admin account can be disabled, which blocks every request immediately, including already-issued sessions.

Admin accounts are completely separate from member accounts. An admin's sign-in method is either local (username and password) or an external provider they have linked (Plex owner account or a Jellyfin administrator account).

## 5. Domain model

### 5.1 Entities

| Entity | Purpose | Main attributes | Identity and uniqueness | Relationships and deletion |
|---|---|---|---|---|
| **Media server** | A connected Plex or Jellyfin instance | name; type; base address; API key (encrypted at rest); enabled | — | Owns libraries and sync runs; deleting the server deletes both. |
| **Library** | A content section on a server (movies, shows, music, …) | server; the library's id on the server; name; library type | Matched by (server, remote id) during sync | Belongs to a server. |
| **Invitation** | A code that grants access | code (up to 20 characters); optional expiry; optional max uses; use count; optional access duration in days; enabled; optional creator; optional pre-wizard and post-wizard | Code is unique. Use count may never exceed max uses when a max is set (enforced by the store). | Many-to-many with target servers and with allowed libraries. If a linked wizard is deleted, the link is cleared. Members created from the invitation outlive it. |
| **Identity** | One real person | display name; optional email; optional expiry; enabled | — | Owns one or more users. Deleting the last user deletes the identity. |
| **User** | One account of an identity on one server | identity; server; originating invitation (optional); the account's id on the server; username on the server; Plex relationship type (friend, shared or home) where applicable; optional expiry; enabled | Unique per (remote account id, server) and per (username, server) | If its invitation is deleted, the link is cleared and the user is kept. |
| **Wizard** | A reusable onboarding flow | name; description; enabled | — | Owns ordered steps; deleting the wizard deletes them. |
| **Wizard step** | One page of a wizard | position (0-based, contiguous); title; formatted content; primary language (default English) | Position unique within the wizard | Owns interactions and translations; both are deleted with the step. |
| **Step interaction** | Something the invitee must do on a step | type (click, timer, terms acceptance, text input, quiz); type-specific configuration; display position | At most one interaction of each type per step | Belongs to a step. |
| **Step translation** | Translated title and content for a step | language code (two-letter standard); title; content | At most one per language per step | Belongs to a step. |
| **Admin account** | A console user | username (3–32, lowercase, letter first, letters/digits/underscore); password hash (absent for external-only); optional email; sign-in method; external account id; enabled; last sign-in; two-factor state (enabled flag, encrypted secret, hashed backup codes, failure counter, challenge nonce, last accepted time window) | Username unique | Owns sign-in sessions and refresh tokens; deleting the admin deletes both. |
| **Sign-in session** | One admin sign-in | hard expiry; last refresh; revoked time and reason (logout, replay, expired, admin); current token generation; user agent and IP for audit | — | Owns a family of rotating refresh tokens. |
| **Refresh token** | One rotating credential inside a session | generation; hashed value; sliding inactivity expiry; consumed time; revoked time | Hash unique; only the hash is stored | Live while neither consumed nor revoked. |
| **Provider sign-in session** | Server-side state for one Plex PIN sign-in attempt | opaque handle; provider; the provider's PIN id; lifetime; provider token (set on success, wiped once used); email; one-time redemption token; redeemed flag | Handle and redemption token unique | Expires at creation plus lifetime; purged by a background job. |
| **Sync run** | Audit record of one synchronisation attempt | server; kind (libraries or users); trigger (automatic, manual, onboarding); outcome (success or failed); start and finish; error message | — | Deleted with its server. |
| **Setting** | A runtime key/value setting | key; value | Key is the identity | — |

Shared rules: every record has a globally unique random identifier and created/updated timestamps; all timestamps are stored and returned in UTC, and a time supplied without a zone is taken as UTC. There is no soft delete; "disabled" is the only reversible deactivation.

### 5.2 Lifecycles and computed states

**Invitation.** There is no stored status. An invitation is **active** when it is enabled, its expiry (if any) is in the future, and its use count is below its max uses (if any). **Remaining uses** is max minus count, never negative, and absent when unlimited. On the dashboard, **pending** means active and never used. A background job turns off invitations whose expiry has passed. The console shows one of five labels, in priority order: Disabled; Used up (has a cap and nothing left); Expired (the server says inactive and the cause is the date); Limited (three or fewer uses left); Active.

**User.** Labels in priority order: Disabled; Expired; Expiring soon (within seven days); Active. Plex users additionally carry a relationship type: **home** (a managed user inside the owner's Plex Home), **shared** (a Plex account that has this server shared with it), **friend** (a Plex friend with no share on this server). The type can be "unknown" until a sync determines it.

**Onboarding** (persisted as a setting): account → security → server → complete. Details in 6.1.

**Sign-in session**: live → revoked (logout, replay, expired) or past hard expiry; deleted by cleanup seven days after revocation or when no live token remains.

**Sync circuit breaker** (in memory, per server): closed → open after N consecutive failures → half-open after the recovery period → closed on success or open again on failure.

### 5.3 Invariants the rewrite must keep

- One remote account maps to exactly one user per server; the same remote id may exist on different servers.
- Use count never exceeds max uses, even under concurrent redemption.
- An invitation always targets at least one server, and its allowed libraries always belong to its target servers.
- Step positions within a wizard are always 0…N−1 with no gaps.
- Every live refresh token in a session has the session's current generation.
- Deleting an invitation or a wizard never deletes members or their accounts.
- Quiz correct answers, server addresses and server ids are never present in anything served to the public join page.
- Media-server API keys and two-factor secrets are never stored in clear and never sent to the browser.

## 6. Core behaviours and workflows

### 6.1 First-run setup

1. **Bootstrap token.** While no admin exists, the backend generates a random one-time token at every start (unless the operator fixed one in the environment), prints it in the server log inside a boxed section together with a ready-made setup link, and writes it to a file readable only by its owner. The token is never served over the network.
2. **Opening the setup link** verifies the token against that file (constant-time) and stores a ten-minute, single-use, same-site-strict authorisation in the browser; the token is removed from the address bar. Without the link, the setup page offers a "paste the token manually" field and a collapsible help section explaining where to find it (container logs, bare-metal console, the shape of the boxed log section, the link format).
3. **Step "Account"**: username (3–32, lowercase, letter first), password (15–128 characters; a four-segment strength meter based on length reads Weak / Fair / Good / Strong), confirmation, optional email. Exactly one first admin can ever be created: concurrent attempts are serialised and only one wins, even with different usernames. On success the creator is signed in immediately.
4. **Step "Two-Factor"** (marked "Recommended"): set up now or later. Setting up shows a QR code and a hidden manual key, then a six-digit verification, then backup codes with "Copy all" and "Download as text".
5. **Step "Security"**: the trusted origin for cross-site protection, pre-filled with the current site address. "Test Origin" compares the typed value with the origin the browser actually sent and shows a green or red result; Save and Skip stay disabled until a test has been attempted, and a failed test makes either button open a warning dialog ("Save Mismatched Origin?" / "Skip Without CSRF Protection?"). If the operator fixed the origin in the environment, the field is read-only with a lock badge and a single Continue. Saving an HTTPS origin automatically turns on secure cookies and says so. Skipping goes straight to the dashboard.
6. **Step "Server"**: identical to the Add Server dialog (6.3). "Skip for now" or "Add Server & Finish" both lead to the dashboard.

Setup resumes at the right step if interrupted. An admin who exists but whose stored step is missing or invalid is sent back to the security step once, so existing installs are forced through the hardening steps. While setup is required, every sign-in method is refused.

### 6.2 Admin sign-in, sessions and two-factor

**Sign-in methods.** Local (always available) plus each external provider that is configured in the environment: Plex (PIN-based sign-in, must be the owner of the configured Plex server, email compared case-insensitively) and Jellyfin (username and password checked against the configured Jellyfin address only, must be a Jellyfin administrator). External sign-in never creates an admin; the external account must already be linked to an admin from the Account settings tab, and an external account can be linked to only one admin. Linking fills in the admin's email if empty. A wrong username and a wrong password produce the same "invalid credentials" message; a disabled account is told so.

**Two-factor (authenticator app).** Standard six-digit, thirty-second codes with one window of drift accepted either side; the issuer shown in the authenticator is the product name and the label is the admin username. Setup generates a secret (stored encrypted), a QR code, and ten single-use backup codes in XXXX-XXXX form; confirming setup with a valid code turns two-factor on and **replaces** the backup codes, so only the codes shown after confirmation count. After a code is accepted, no code from that time window (or an earlier one) is accepted again. Five failed attempts block verification until fifteen minutes after the last failure or until a success. Backup codes are case- and whitespace-insensitive and each works once; they can be regenerated with a valid code. Disabling requires the password and a valid code and clears everything.

When two-factor is on, a correct password (or successful external sign-in) does **not** start a session; it returns a five-minute challenge bound to a single-use nonce on the account. The client then submits a code or backup code. The code is verified before the nonce is consumed, so a typo does not burn the challenge, but a successful challenge cannot be replayed. The sign-in UI shows six single-digit boxes with auto-advance, paste support and auto-submit, and a "Use a backup code instead" switch.

**Sessions.** Every completed sign-in starts a new, independent session that lasts at most fourteen days and is never extended. The browser holds two HTTP-only, same-site cookies: a fifteen-minute access token naming the admin and the session, and a refresh token with a seven-day inactivity limit (capped by the session's hard expiry). Every authenticated request verifies that the admin exists and is enabled and that the session is neither revoked nor past its hard expiry, so logout or replay detection cuts off access at once. Refreshing rotates the token: the presented token is consumed, siblings of its generation are revoked, a successor of the next generation is issued. If a client presents the token consumed by the latest rotation whose successor was never used (a lost reply, or two tabs refreshing together), it receives another sibling, up to three live tokens per session. Any other reuse is treated as replay and revokes **that session only**; the admin's other devices stay signed in. Logout ends only the current session and always reports success. Renewal is invisible to the admin: the web layer renews once on a rejected access token and retries once; a slow or unreachable backend keeps the session and shows "Authentication temporarily unavailable" rather than logging the admin out, because a lost refresh reply used to revoke every session.

**Profile.** The admin can change their email, change their password (local accounts only; current password required; 15–128 characters), link a provider, and manage two-factor. Changing password or email does not end other sessions.

### 6.3 Media server management

**Add a server** (dialog, also the setup step): name (required), type (segmented toggle of the registered providers, tinted with the provider's brand colour), address (full URL including scheme) and API key (masked, with provider-specific help about where to find it). If the operator has supplied complete credentials for a provider in the environment, a banner offers them with one button per provider; choosing one swaps the fields for read-only "Configured in environment" boxes.

**Test Connection is mandatory.** The submit button stays disabled until a test succeeds, and changing any connection field clears the result (a late result for stale fields is discarded). With a type chosen, only that type is probed; without one, every provider is probed concurrently with a ten-second limit each and the first success wins, switching the type to the detected one. Success shows the detected product, the server's name and version. Failure is shown as a message, never as an error page. Server addresses must be http or https; the system can optionally refuse private, loopback, link-local and similar addresses (and hostnames that resolve to them), but allows them by default because self-hosting is the normal case.

**On create**, the key is encrypted and stored, then two best-effort syncs run immediately (libraries, then a user import), recorded with the "onboarding" trigger; their failure does not fail the add. Creating the first server completes the onboarding server step.

**Environment overrides.** Per provider type, an address and/or key in the environment overrides the stored values for every server of that type, independently per field. The console shows those fields with an "Environment Variable" lock badge, and the key is displayed as "Set via environment variable". Environment keys are never sent to the browser; the detection list exposes only booleans, and a masked preview shows at most the first and last four characters.

**Server detail** shows information, libraries (name, type, remote id), a sync status panel for libraries and for users (next scheduled time with a live countdown, "Syncing now...", last completed, and circuit-breaker state as "Circuit Open" with the failure count, "Recovering", or "N recent failures"), and actions: Sync Users, Sync Libraries, Reset Circuit Breaker (only while open) and Delete Server. The page refreshes itself every fifteen seconds while open.

**Delete** removes the server, its libraries and its sync history, and warns that local member records will be lost while accounts on the media server itself are untouched. There is no edit-server screen; to change an address or key the admin deletes and re-adds (see section 12).

### 6.4 Synchronisation

**Library sync** fetches the server's libraries and reconciles by remote id: new ones are added, changed names or types are updated (counted only when something actually changed), missing ones are removed. The result dialog shows total, added, updated and removed. Invitations' allowed-library links to a removed library are affected (see 12).

**User sync** compares the server's accounts with local users by remote account id and classifies them as **matched**, **orphaned** (on the server, not local) and **stale** (local, not on the server). A manual run is a **dry run by default** and changes nothing; the result dialog is titled "All Matched" or "Discrepancies Found" and lists imported and stale usernames. A real run imports each orphan as a new identity (display name = server username, email from the server if known, no expiry, no invitation link) and, for matched users, refreshes the Plex relationship type and fills in a missing identity email from the server without ever overwriting an existing one. Sync never changes a user's enabled state and never deletes. Running it twice is a no-op. Administrators on Jellyfin are included in the import.

**Scheduler.** Four repeating jobs start with the application and are all tolerant of individual failures:

| Job | Cadence | Behaviour |
|---|---|---|
| Invitation expiry | default hourly, minimum one minute | Disables every enabled invitation whose expiry has passed. |
| Media server sync | default every fifteen minutes, minimum one minute; first run fifteen seconds after start so startup is not blocked | For each enabled server: library sync for all, then user sync with import for all. |
| Session cleanup | same as expiry | Deletes sessions past hard expiry, revoked more than seven days ago, or with no live token. |
| Provider sign-in cleanup | same as expiry | Deletes expired PIN sessions. |

Each server's sync phase has its own time limit (default five minutes), a small number of retries with exponential backoff and jitter (honouring a "retry after" hint from the server), and a **per-server circuit breaker** covering both phases: it opens after three consecutive failures by default, skips that server (recording each skip as a failed run with the reason), lets one trial through after the recovery period (default five minutes), and closes on success. Permanent failures (invalid token, user not found, username taken, permission denied, validation errors) and unknown errors are never retried. Breaker state is in memory and resets on restart; the admin can reset it from the server page. Every automatic, onboarding and non-dry manual run writes a sync-run record, which feeds the dashboard's recent activity.

### 6.5 Invitations

**Create** (dialog titled for creating an invitation "with optional restrictions"): target servers as toggle tiles (at least one; every chosen server must exist and be enabled), allowed libraries as toggle pills filtered to the chosen servers (none selected means all libraries), an optional custom code (1–20 letters or digits; placeholder suggests a readable word-style code), optional expiry date and time (must be in the future), optional maximum uses (positive whole number; empty means unlimited), optional access duration in days (positive; empty means permanent), optional pre-registration and post-registration wizard (drop-downs listing enabled wizards plus "None"), and an enabled switch. A generated code is twelve characters from capital letters and digits excluding 0, O, I and L, drawn from a cryptographic random source, retried a few times on collision. A duplicate code is reported clearly. Codes are matched exactly (case-sensitive).

**List** is paginated (default fifty per page, capped at one hundred), filterable by enabled state and by expired/active, sortable by created date, expiry or use count in either direction, with the state kept in the address bar so views can be bookmarked. Columns: code chip, status badge, uses ("3 / 10" plus "(7 left)" when capped), expiry ("Never" or the date with "(expired)"), created, and row actions: copy invite link (copies the public join address for the code and toasts "Invite link copied"), view, edit, delete. The copy link is the primary way an admin shares an invitation.

**Detail** shows read-only facts ("These fields cannot be modified after creation."): code, use count with remaining, created, created by, last updated; the target servers; allowed libraries (only when restricted); attached wizards with a shortcut to open each; and an edit card ("Changes take effect immediately") for enabled, expiry, max uses, access duration, target servers, libraries and both wizards. Code, use count, creator and creation time are immutable. Leaving a field out leaves it alone; explicitly clearing expiry, a limit or a wizard means "none". Libraries are re-validated against the (new) target servers. Deleting shows "Users who have already redeemed this invitation will not be affected."

**Validation order** for a code (used by the public page and by redemption): not found → expired → disabled → max uses reached. Validating never changes the use count.

### 6.6 The public join flow

The invite link opens the join page for a code. The page tells the browser not to send its address to other sites, so the code cannot leak through the referrer when the invitee is sent to a sign-in provider. Progress for each code (which wizard stages are done, the registration result) is kept per browser tab so a refresh does not lose it, and the page scrolls to the top on every stage change (respecting reduced-motion preferences).

1. **Validation** runs on load. An invalid code shows a rose "Invalid Invitation" card with the precise reason (does not exist / disabled by the administrator / expired / reached its maximum number of uses). A valid code shows an emerald "Valid Invitation" card with the access duration ("Your access will be valid for N days after registration"), the target servers (name and type only; addresses and ids are deliberately withheld), the allowed libraries or "Access to all libraries on target servers", an amber "Additional Steps Required" notice when a pre-registration wizard is attached, and a Continue button.
2. **Server check.** Pressing Continue probes each target server concurrently with a ten-second limit. Unreachable servers produce a toast, a rose "Server Connection Issue" panel listing each server with an "unreachable" marker, and Retry / Continue Anyway buttons. If the code has meanwhile become invalid, the invitee is told. Any other failure of the check itself lets the invitee proceed.
3. **Pre-registration wizard**, if attached (6.7). Cancelling returns to the validation card and clears progress.
4. **Registration.** The form depends on the target servers' join style:
   - **Credential servers (Jellyfin)**: "Create Your Account" with username (3–32, lowercase, letter first, letters/digits/underscore), password (8–128, with show/hide) and optional email ("Used for password recovery and notifications").
   - **Sign-in-link servers (Plex)**: "Sign in with Plex". A popup opens the provider's sign-in; the page polls every two seconds and shows "Waiting for authentication...", switching to "Reconnecting... (N checks missed)" after missed polls, with "Open Plex Again" and Cancel. No PIN code is ever shown to the invitee. On success it shows "Signed in as <email>", quietly derives a username from the email (lowercased, letter first, only letters, digits and underscores), and proceeds to "Adding you to the server...". An expired sign-in offers Try Again.
   - If an invitation mixes both kinds of server, the credential form is used and the Plex sign-in is still required for the Plex target.
5. **Redemption** (server side, in this exact order):
   1. If a one-time provider redemption token was supplied, exchange it atomically for the provider token and email; the provider token is wiped from storage once exchanged. An invalid token is ignored at this point and surfaces as "sign-in required" later.
   2. **Reserve one use atomically** (increment only if still enabled, unexpired and under the cap). If the reservation fails, report the reason; if the invitation looks valid but the increment did nothing, another request took the last slot and the answer is "maximum uses reached".
   3. If a pre-wizard is attached, require a signed completion token for that exact wizard, at most one hour old.
   4. For every Plex-style target: require a provider token, from the matching provider.
   5. Reject the username if it already exists locally on any target server.
   6. Create the account on each target server, one after another, passing that server's allowed libraries. Only the connection phase is retried (a handful of attempts with backoff); the create call itself runs exactly once.
   7. Compute the access expiry from the duration, if any, and apply it to the identity and every user.
   8. Remove any stale local record for the same remote account on the same server (an earlier import or a previous invitation cycle), deleting an identity left empty.
   9. Create the identity (display name = username; email = form email, else the provider email, else the first email any server reported) and one user per server, linked to the invitation.
   10. After success, in the background and non-blocking: apply library restrictions (skipped for Plex friend invites, where libraries were set at invite time) and the default permission set — streaming on, transcoding on, downloads off, offline sync off. Failures here are logged only; the member already has access.

   **If anything fails after the reservation**, the whole local transaction rolls back (releasing the reserved use and leaving the redemption token usable), and every account already created on other servers is deleted again, best effort, one by one. Failures are reported with a precise cause (username taken, server connection failed, invalid invitation, validation error, or a generic registration failure), the name of the failed server, and a "Partial Success" card listing any accounts that had been created, with Try Again returning to the right form. Redemption is deliberately not idempotent: a second successful call is a second use.
6. **Post-registration wizard**, if attached. Cancelling here goes straight to success because the account already exists.
7. **Success**: "Account Created Successfully!", the created accounts (username and remote id), an "Open Plex" button when a Plex server was a target (pointing at the Plex web app, never at the server's internal address), and a "What's Next?" list (download a player, connect, sign in).

### 6.7 Wizards

A wizard is a named, reusable sequence of steps that can be attached to any number of invitations as a pre-registration flow (completed before an account exists; completion is enforced) and/or a post-registration flow (shown after creation; cancellable).

**Authoring.** The builder has a details card (name required, description up to 2,000 characters, enabled switch) and a steps card. Steps must be added after the wizard is first saved. Each step row shows a drag grip, its order number, gold pills naming its interactions or "Content only", its title, and edit/delete controls; steps are reordered by dragging (positions stay contiguous and are renumbered on delete). The step editor has a title, a formatted-text editor with Edit and Preview tabs and a toolbar (bold, italic, heading, link, image, bullet and numbered lists, quote, code), a "Primary language" indicator, a translations area, and five interaction "modules" with on/off switches. Turning a module on or off saves immediately; module settings validate as you type and auto-save shortly after a valid change. A header Preview button opens a full-screen dark overlay with a "PREVIEW MODE" tag showing the end-user wizard exactly as invitees will see it, without saving progress.

**Content safety.** Step content is rendered through a strict allow-list everywhere (builder preview, admin preview, public page): headings, paragraphs, emphasis, links, lists, quotes, code, images and rules only; scripts, styles, frames, embedded objects, event handlers, script-scheme links and tables are stripped; every link opens in a new tab without opener or referrer. This is tested against randomly generated hostile input.

**Translations.** A step has a primary language and any number of translations (title and content) keyed by two-letter standard language codes; the full list of about 183 languages with native names is served by the backend, English first. The invitee sees a language switcher on steps that have more than one language; the choice is remembered for the session, and a step lacking that translation falls back to its primary language. Saving a step replaces its translation set wholesale. "Set as Primary" swaps a translation with the primary content.

**Interactions.** A step may have zero interactions (informational) or several, and all must be completed. At most one of each type per step.

| Type | Admin configuration | Invitee experience | Completion rule |
|---|---|---|---|
| Click confirmation | Button text (default "I Understand") | One prominent gold button | Acknowledged |
| Timed wait | Duration 1–300 seconds (default 10) | A circular countdown ring showing M:SS, pulsing in the last five seconds, "Ready!" at zero; completes itself | The configured real time has elapsed since the start the client recorded |
| Terms of service | Checkbox label (default "I accept the terms of service") | A card-style checkbox and "Accept & Continue" | Accepted |
| Text input | Label (required), placeholder, required flag (default on), min and max length (min ≤ max) | A labelled field with a live character counter; Enter submits | Non-blank if required; length within bounds |
| Quiz | Question, 2–10 options, the correct option | Option buttons behaving as radio buttons, "Submit Answer"; green "Correct!" or an "Incorrect answer — wait Ns" cool-down that grows from three to ten seconds | Chosen option equals the correct one; the correct index is never sent to the browser |

**Ordering is enforced server-side.** Each step is validated by the backend before the invitee can advance. The first step needs nothing; every later step must present a signed progress token, at most one hour old, for the same wizard, listing exactly the earlier steps in order. Passing a step returns an extended token; passing the last step returns a signed completion token (one hour) that redemption accepts as proof. Editing a wizard's steps invalidates in-flight tokens. Going back clears completions of the current and later steps. The submitted set of interactions must exactly match the step's set.

### 6.8 Managing members

The users list ("Manage users across all connected media servers") has no create button; members come only from redemptions and imports. It offers debounced free-text search (contains-match over username, remote id, display name, identity email, server name, server type and invitation code), filters by server, invitation, enabled state and expiry, sorting by created date, username or expiry, and pagination. Columns: username with email beneath, server (provider badge, Plex relationship badge, server name), status, expiry ("Never", "(expired)", "(soon)"), created, invitation code, and actions (view; enable/disable only for server types that support it; delete).

**User detail** shows user information (username, type with explanation, remote id, status, dates), a permissions card with only the switches the server type supports (Streaming, Downloads, Sync, Transcoding; each saves immediately on the media server and reverts on failure; all locked while the user is disabled), the media server, the identity (the unified person across servers), the source invitation with a shortcut, linked users (other accounts of the same identity, as clickable tiles) and actions.

Rules: enable/disable changes the media server first and the local record only on success; it is refused without contacting the server for types that do not support it (Plex). Permission changes are applied on the server only and nothing is stored locally. Delete removes the account on the server first, then locally; if the server says the account does not exist, the delete is refused unless forced, in which case only the local record goes. Deleting an identity's last user deletes the identity; there is no single "remove this person from every server" action.

For Plex the delete dialog is stepped by relationship type: a **shared** user goes through "Remove Shared Access" (libraries unshared, friendship kept, local type becomes friend) then "Remove Friend"; a **friend** has a single "Remove Friend" step; a **home** user has "Remove from Plex Home"; every other user has a single "Delete User" step covering both the server and the local record.

### 6.9 Dashboard and logs

**Dashboard**: four stat cards (Total Invitations with "N currently active"; Active Users "of N total"; Media Servers "N enabled"; Pending Invites "awaiting first use") and a Recent Activity feed of the ten newest events across member created, invitation created, sync completed and server added, with relative times. No auto-refresh.

**Logs**: a live stream of the application's own structured log entries, held in a server-side ring buffer of the last 5,000 entries (lost on restart). On connect the viewer receives up to the most recent 500 matching entries, then new ones as they occur; a heartbeat keeps the connection alive, the server closes it after thirty minutes and the client reconnects without repeating entries. The toolbar has a connection light (Connecting / Live / Disconnected), pause/resume (new entries keep collecting while paused), a minimum-level filter with quick-filter pills showing error and warning counts, a source filter, a debounced search bound to the find shortcut, Clear and Clear Filters, and an entry-count badge. Rows are colour-coded by level, show relative time (exact time on hover), level, source, message and up to three key/value chips; selecting one opens a detail panel with the full entry and "Copy as structured text"; arrow keys move the selection. The list follows the newest entry until the admin scrolls up, then offers "Jump to latest". The stream's own requests are excluded from logging so it cannot feed itself, and request logs never include bodies, headers or cookies.

## 7. External integrations

### 7.1 Common provider contract

Each provider declares display metadata (name, brand colour, icon, API-key help text), which environment settings override its address and key, its capabilities, its supported permission keys, its admin sign-in style, its join style, and whether it offers a PIN sign-in. Every provider client can: test the connection (never throws), read server name and version, list libraries, create a user, delete a user, enable/disable a user, set library access, update permissions, remove shared access, and list users. The universal permission vocabulary is download, stream, offline sync and transcode; each provider maps what it can and ignores the rest. The UI is generated from these declarations, so no screen hard-codes a product.

| Capability | Plex | Jellyfin |
|---|---|---|
| Connection | server address plus the owner's Plex token | server address plus an administrator API key |
| Create / delete user | yes / yes | yes / yes |
| Enable / disable | **no** (access is revoked only by unsharing or deleting) | yes |
| Library restriction | yes, applied at share time | yes, applied after creation |
| Supported permission toggles | download only (maps to Plex "allow sync") | download, stream, offline sync, transcode |
| Password at creation | no (the invitee uses their own Plex account) | yes |
| Join style | invitee signs in with Plex (required) | invitee chooses username and password |
| Admin sign-in | Plex PIN sign-in; must be the server owner | Jellyfin credentials; must be an administrator |
| Remove shared access but keep friendship | yes | not applicable |
| User listing | friends and home users, classified by whether this server is shared with them; includes email when Plex provides it | all accounts, no email; administrators included |

### 7.2 Plex

Plex involves two systems: the local server (name, version, library sections, machine identifier) and the Plex cloud account service (the owner's account, friends and home users, invitations, sharing, PIN sign-in, member email). Every Plex operation runs under a configurable timeout (default thirty seconds). Errors from Plex are classified into already-friend, username taken, not found, invalid token, timeout, connection, rate limited, permission denied and generic; rate limiting is treated as temporary.

**Account creation** depends on what the invitee provided:

- Email **and** their own Plex sign-in (the normal path, since the join page requires Plex sign-in): **direct share** of this server to their account with the chosen libraries, creating no friendship; any leftover relationship from an earlier invitation is first removed; then, in the background, the pending share is accepted on their behalf (a few attempts) and stale pending invites to that email are cancelled. Type: shared.
- Email only (fallback): a standard friend invitation the invitee must accept; if Plex says they are already a friend, the orphaned relationship is removed and the invite retried once. Type: friend.
- No email: a managed **home** user inside the owner's Plex Home.

Deletion matches the member by numeric id (falling back to email or username for legacy records), removes this server's share first, then removes the home user or the friendship; success if either removal worked. Library and permission edits apply to the member's access on this server and only work for people present in the owner's friends or home list.

**PIN sign-in** (used by invitees and by admin sign-in): the backend asks Plex for a PIN (retrying on transient failures), stores the attempt under an opaque random handle (so Plex's sequential PIN ids are never exposed) with a ten-minute lifetime, and returns the handle, the Plex sign-in link and the expiry. The client opens the link in a popup and polls the handle every two seconds. When Plex reports success, the backend fetches the member's email and returns a **one-time redemption token** plus the email; the raw Plex token never reaches the browser. The redemption token is exchanged exactly once, atomically, server-side.

### 7.3 Jellyfin

Connection uses the server address and an administrator API key; the test reads system information. Creating a member creates the user by name and then sets its password; Jellyfin stores no email. "Already exists" replies become "username taken". Library restriction turns off "all libraries" and sets the enabled list. Enable/disable toggles the account's disabled policy flag. Connection-type failures (timeouts, DNS, refused, 5xx, unauthorised) are classified as external-service errors; everything else as media-client errors.

### 7.4 Failure handling across integrations

- Polling versus push: everything is polling. There are no webhooks from the media servers.
- Connection tests and join-page health probes are bounded at ten seconds per server.
- Sync uses retries with backoff plus a per-server circuit breaker; redemption retries only the connection phase.
- Partial data is tolerated: a server that cannot be reached is skipped and recorded as a failed run; missing emails are back-filled later by sync; an unknown Plex relationship type is shown as "run a sync to detect".
- Any upstream failure is surfaced to the admin with the correlation id that also appears in the logs.

## 8. User interface

### 8.1 Information architecture

| Area | Screens |
|---|---|
| Root | Redirects signed-in admins to the dashboard and everyone else to sign-in. |
| Auth (centred card under logo and wordmark, theme toggle top-right) | Sign-in; first-run setup (four-step indicator: Account, Two-Factor, Security, Server). |
| Admin (fixed left sidebar on desktop, slide-in drawer with dimmed backdrop on narrow screens; sticky header with section title and theme toggle; footer with username and a log-out icon) | Dashboard, Invitations (list, detail), Users (list, detail), Servers (list of cards, detail), Wizards (list of cards, new, edit with preview), Logs, Settings (General, Account, Sync & Tasks, About). |
| Public (minimal sticky header) | Join page for a code. |

Access rules: admin pages require a signed-in admin; an admin who has not finished setup is sent to setup from every page; a signed-in admin opening sign-in or setup is sent to the dashboard. When the backend is unreachable, the sign-in page shows "Connecting to server..." and retries every three seconds — this is the first screen a container user sees while the backend boots.

### 8.2 Interaction patterns

- Data loads before a page is shown; skeleton placeholders appear only during an explicit "Try again". Error panels (rose, with an alert role) say "Connection Error" when the server could not be reached, otherwise a page-specific title, plus the message and a retry button. Empty states (dashed panel, status role) always explain how the list will fill and often offer the primary action.
- Lists keep filters, sort and page in the address bar; changing a filter returns to page one. Pagination reads "Showing X to Y of Z items" and "Page N of M" with first/previous/next/last buttons.
- Toasts confirm every action ("Invitation deleted", "User enabled", "CSRF origin saved", …). Error toasts are sanitised: anything resembling a stack trace, file path, database text or internal code, or longer than 200 characters, becomes "An unexpected error occurred"; known error causes get friendly text ("This username is already taken. Please choose another.", "Media server is unreachable", "This invitation is no longer valid").
- Confirmation dialogs carry a round warning icon coloured by severity, a title, a description, Cancel and a coloured confirm button; buttons disable and the close control hides while working.
- Status badges are pills with a glowing dot and a text label, so colour is never the only signal.
- Settings lock: any value supplied by the environment shows an "Environment Variable" badge with a lock icon and cannot be edited.

### 8.3 Real-time and refresh

The log viewer is a live stream. The server detail page polls every fifteen seconds and its sync countdown ticks every second. Permission switches save immediately. The join page polls the Plex sign-in every two seconds. Everything else refreshes on navigation or after an action.

### 8.4 Accessibility and localisation

Measures in place: spoken labels on icon-only buttons, current-page marking in navigation, expanded/collapsed announcement on the mobile menu, status and alert roles on empty and error states, a live region for wizard progress, proper roles for switches, radio groups (quiz), checkboxes (terms), pressed toggles (server and library pickers, log rows), autocomplete and one-time-code hints on inputs, visible focus rings, red outlines on invalid inputs, Escape to close menus and panels, arrow-key navigation in the two-factor boxes, language menu and log list, and reduced-motion handling for the wizard, join page and preview glow. Gaps: no skip-to-content link; a few icon-only buttons (wizard delete, step delete, translation and quiz-option remove, open-wizard shortcut) lack names; step reordering is drag-only.

The admin console and the join-page shell are English only, with fixed US-style date formatting. Localisation exists only for wizard step content, authored per language by the admin and switchable by the invitee. A rewrite should plan interface localisation from the start (see 12).

## 9. Configuration and operations

### 9.1 Deployment shape

A single self-hosted instance made of two cooperating processes: the backend (API, scheduler, provider clients) and the web layer (renders the UI, relays every browser call to the backend over an internal address, and relays the backend's cookies). Browsers talk only to the web layer, so no cross-origin configuration is needed; an optional mode lets browsers call the backend directly, which then requires allowed-origins configuration and, in the container with its built-in VPN enabled, explicitly exposing the backend port on the LAN. A container image bundles both under a process supervisor, defaults the backend's trusted origin to the public origin, writes the bootstrap token under its data folder, prints the setup link, and uses a shorter shutdown drain that fits the container runtime's stop timeout. Both processes have health, liveness and readiness probes.

The persistence layer is a relational store. A lightweight embedded file-based store is the default and suits single-worker deployments; a full client-server relational store is supported for production. The embedded store imposes a single-writer constraint, which is why the backend runs one worker in development and the first sync waits fifteen seconds after start. Schema changes are applied by versioned migrations run separately from the application; a test verifies that applying every migration yields the model schema and rolling back removes everything.

### 9.2 Operator settings (environment)

| Setting | Default | Notes |
|---|---|---|
| Application secret | required, at least 32 characters; startup fails without it | Signs tokens and derives the separate encryption keys for server API keys and two-factor secrets. **Changing it invalidates stored server keys, two-factor secrets, sessions and wizard tokens.** The dev launcher generates and saves one. |
| Persistence connection | embedded file store | Either supported store engine. |
| Listen address and port | all interfaces, backend port 8000; web port 3000 | |
| Debug mode | off | Enables API documentation pages, relaxes the trusted-origin requirement with a warning, enables a test-only PIN completion endpoint, and is a precondition for the development auth bypass. Never for production. |
| Public origin | unset | The address people open in the browser. Required for plain-HTTP deployments; without it the web layer assumes HTTPS behind a proxy that preserves the host, and sign-in and saving fail with one startup warning. Must be a bare scheme-host-port origin or the web layer refuses to start. |
| Trusted origin for cross-site protection | unset; the container defaults it to the public origin | When set, locks the console value. A value saved during setup is used when neither is set. |
| Secure cookies | off | Locked whenever present. The web layer independently marks relayed cookies secure exactly when the public origin is HTTPS, so this only matters for clients calling the backend port directly. |
| Allowed cross-origin sites | none (cross-origin disabled) | Only for the direct-to-backend mode. |
| Bootstrap token and its file location | generated per start while no admin exists; file next to the data store | Fixing a token is optional. |
| Invitation expiry check interval | one hour, minimum one minute | Also drives session and PIN cleanup. Locks the console value. |
| Sync interval | fifteen minutes, minimum one minute | Locks the console value. |
| Per-server sync timeout, retry count, backoff base, circuit threshold, circuit recovery | 5 min, 2, 2 s, 3, 5 min | Bounded ranges; out-of-range values stop startup. |
| Plex request timeout | 30 s, minimum 5 | |
| Allow private-network server addresses | on | Turn off for public or multi-tenant hosting to block server-side request forgery. |
| Per-provider address and key | unset | Override stored values field by field for every server of that type; also enable that provider's admin sign-in. |
| Forwarded-address header and proxy depth | off | Trust only when every request passes through the proxy, or clients can forge their address. |
| Forwarded protocol/host headers | off | Only without a public origin, behind a trusted proxy. |
| Shutdown drain, body size limit, idle timeout | 30 s, 512 KB, 10 s | Live streams are exempt from the idle timeout. |
| Development auth bypass | off | Treats every request as a stand-in admin; debug only. |

### 9.3 Console settings

General: trusted origin (with Test) and secure cookies. Sync & Tasks: sync interval and expiration check interval, each 60–86,400 seconds with a live "Every 15 minutes" preview. Account: email, linked provider, password, two-factor. About: application version, runtime version, persistence engine and operating system. Each value reports whether it is locked by the environment. Note that intervals saved here are stored and displayed but do not currently change the running scheduler (12).

### 9.4 Operations

- **Logging**: structured entries with a correlation id on every error response; the in-memory ring buffer feeds the console's log viewer; request logs record method, path, content type and parameters only.
- **Health**: overall (healthy or degraded with a persistence check), liveness, readiness. Unauthenticated and hidden from API documentation.
- **Shutdown**: the web layer drains in-flight requests up to the configured deadline on stop or hang-up signals, ends live streams cleanly so log viewers reconnect quietly, and exits at the deadline even if backend calls are pending. The scheduler waits up to ten seconds for jobs.
- **Backups**: back up the data store and the application secret together; the store is useless without the secret because keys and two-factor secrets are encrypted with it.
- **Upgrades**: apply migrations, then start. Migration history is incremental since the session rework; earlier history was squashed repeatedly while the project was unreleased.
- **Privacy posture**: Zondarr stores member usernames, remote account ids, optional emails and Plex relationship types; it stores no media activity, no passwords of members, and no provider tokens beyond the ten-minute sign-in window. Sign-in sessions record user agent and IP for audit. Nothing is sent to third parties except the media servers and the Plex account service. Web fonts are currently loaded from a hosted font service, which a privacy-conscious rewrite should bundle instead.
- **Developer launcher**: a single command runs both processes for local development with preflight checks (environment file, toolchains, free ports, folders), dependency sync, migrations, an auto-generated secret saved with owner-only permissions, one backend worker, readiness wait, process-id files and a stop command. It is tooling, not product.

## 10. Security

- **Authentication**: cookie-carried short-lived access tokens plus rotating refresh tokens as described in 6.2; a bearer header is also accepted for scripts. Access checks are evaluated on every request against the live session, so revocation is immediate.
- **Passwords**: memory-hard hashing with silent re-hash on parameter change. Admin passwords are 15–128 characters; member passwords on Jellyfin 8–128. There is no lockout on password sign-in (gap); two-factor verification is rate-limited.
- **Two-factor**: encrypted secret, hashed single-use backup codes, time-window replay protection, nonce-bound challenge, five-attempt limit with fifteen-minute cooldown. External sign-in must also pass two-factor.
- **Cross-site protection**: an origin check on every state-changing request at both layers. The web layer refuses any write whose Origin header is not exactly the public origin (a missing Origin counts as foreign). The backend compares Origin (or Referer, reduced to scheme, host and non-default port) against the trusted origin, case-insensitively and ignoring a trailing slash; requests with neither header pass because they cannot come from a browser; sign-in, setup, public join and health routes are exempt; in production with no trusted origin configured, every browser write is refused. The trusted-origin value is cached for sixty seconds.
- **Secrets at rest**: media server keys and two-factor secrets encrypted with authenticated symmetric encryption under purpose-separated keys derived from the application secret. Refresh tokens stored only as hashes. Environment-supplied keys are never sent to the browser.
- **Bootstrap**: one-time token via log and owner-only file, never via the network; constant-time comparison; single-winner first-admin creation; single-use ten-minute browser authorisation; external sign-in blocked until an admin exists; no auto-provisioned admins.
- **Public surface hardening**: the public validation response omits server addresses, ids and quiz answers; wizard order and completion are proven by signed, short-lived tokens; Plex PIN ids are hidden behind opaque handles; the raw Plex token never reaches the browser and is wiped after one exchange; the join page suppresses the referrer; redemption tokens are bound to their provider so a token from one provider cannot be replayed against a server of another.
- **Server-side request forgery**: server addresses must be http(s); optional blocking of private, loopback, link-local, reserved, multicast and unspecified targets, including hosts that resolve to them.
- **Content safety**: wizard content rendered through a strict allow-list; error messages shown to users never include internal details; API documentation only in debug mode.
- **Relay hygiene**: the web layer strips connection-control, internal and client-supplied forwarded headers before relaying, bounds backend calls (two minutes, or until the reply starts for the long operations: server add, syncs, redemption), cancels them when the visitor leaves, and never cuts off a token refresh.
- **Trust assumptions**: the instance is on a trusted network or behind a reverse proxy that preserves the host; all admins are fully trusted; forwarded-address headers are trusted only when explicitly configured.

## 11. Non-functional requirements

- **Scale**: a single owner's servers (typically one to a few), hundreds to low thousands of members, dozens of invitations. Lists are paginated at fifty (max one hundred) with server-side search; the user list was designed for more than a thousand members.
- **Latency**: pages load their data before rendering; the first sync is delayed fifteen seconds so startup requests are never blocked; heavy provider libraries are loaded lazily so first page load is fast.
- **Reliability**: idempotent sync; per-server timeouts, retries and circuit breakers so one dead server never stalls the others; atomic use reservation; full rollback of partially created accounts; lost-reply recovery on session refresh so a flaky network does not sign admins out; graceful shutdown with draining.
- **Concurrency**: single backend worker on the embedded store (single-writer constraint); the client-server store supports multiple workers, with a store-wide lock serialising first-admin creation and row locks serialising refresh rotations per session.
- **Resource bounds**: 5,000 log entries in memory server-side, about 2,000 in the browser; log streams capped at thirty minutes; request bodies capped at 512 KB; PIN sessions ten minutes; tokens and challenges short-lived.
- **Accessibility target**: WCAG 2.1 AA (mostly met; gaps in 8.4).

## 12. Known weaknesses and improvement ideas

Concrete problems found in the source and history, with generic directions for the rewrite:

1. **Member expiry is never enforced.** The access duration sets an expiry on identities and users and the UI shows "expired", but no job disables or removes expired members. The original design called for a configurable policy (disable or delete). Build the policy and the job, and surface "what will happen on expiry" on the invitation.
2. **Intervals saved in the console do not change the running scheduler**, which reads its intervals only at startup. Make the scheduler observe setting changes.
3. **No edit-server screen.** Changing an address or key requires delete and re-add, which loses libraries, sync history and member links. Provide server editing with a re-test requirement, and make the re-test work with the stored (encrypted) key.
4. **No admin management.** After the first admin there is no way to create, list, disable or delete other admins in the product. Add it, with an audit trail.
5. **Invitation-level permissions are accepted but ignored.** The design promised per-invitation permissions (downloads, live TV, camera upload, concurrent sessions); redemption always applies a fixed default set and the create form does not expose permissions at all. Either implement per-invitation (and per-server) defaults or remove the field.
6. **The permissions editor does not load current values**; every switch starts as "on". Read the real state from the server before rendering.
7. **Cascade behaviour on server and library deletion is store-dependent.** Users reference servers without a cascade rule, and invitation links to removed libraries are not cleaned explicitly. Define the rules (delete local users with their server; drop stale library links) and enforce them in the domain layer, not the store.
8. **Max uses can be set below the current use count**, which surfaces as a generic error from the store constraint instead of a clear validation message.
9. **Disabled wizards are still shown and required**, and a pre-wizard with no steps makes its invitation unredeemable. Treat a disabled or empty wizard as absent, or block attaching one.
10. **The timer trusts a client-supplied start time**, so a client can backdate it. Record the start server-side when the step is first served.
11. **No lockout or rate limit on password sign-in** (only two-factor is limited) and no general request rate limiting on public endpoints (code validation, PIN creation). Add both; invitation codes are short enough to enumerate.
12. **Invitation codes are case-sensitive**, so a custom mixed-case code is fragile when typed. Normalise codes on create and lookup.
13. **Linking an external sign-in blocks password changes** although password sign-in still works. Model sign-in methods as a set rather than a single value.
14. **Plex edge cases**: a share that times out after Plex has already applied it leaves a share with no local record; directly shared members without a friendship may not appear in Plex's friends list, so later permission edits report "user not found"; an invited friend not yet visible is stored under their email "as a last resort". A rewrite should reconcile Plex shares by machine identifier and account id after every write and during sync.
15. **Jellyfin administrators are imported as managed members** during sync. Flag or exclude server administrators.
16. **An invalid Plex redemption token is silently ignored** at redemption and surfaces as "sign-in required". Report the real reason.
17. **Interface localisation is absent**; only wizard content is translatable, and dates are fixed US-style. Internationalise the admin console and the join shell from the start and respect the invitee's locale for dates.
18. **Technical jargon in the UI** (trusted origin, circuit breaker, environment variable, event stream) and inconsistent capitalisation. Write user-facing explanations and a capitalisation rule.
19. **Stale copy**: the empty servers state says servers are "configured in the backend" although an Add Server button exists; the add-server submit button reads "Testing Connection..." while saving; the success page's "Sign In" step assumes a password even for Plex members.
20. **Accessibility gaps**: no skip link, several unnamed icon buttons, drag-only step reordering (add move up/down controls).
21. **Setup can be skipped** past the trusted-origin and server steps. That is intentional for flexibility, but the dashboard should then show a persistent reminder.
22. **Secret rotation is destructive.** Changing the application secret bricks stored keys, two-factor secrets and sessions. Support key rotation with re-encryption, or at least a guided re-entry flow.
23. **Pending redemption is not idempotent** and the use count is consumed per success; consider a short-lived idempotency key on the join page so a double-submit cannot create two members.
24. **Only two providers.** The provider abstraction is sound; Emby and other servers were envisioned but never added. Keep the capability-declaration model so new providers need no UI changes.
25. **No notifications.** There is no way to tell the owner that someone joined, that a sync keeps failing or that a circuit opened; the dashboard feed is the only signal. A notification-service integration (as a category) is the most requested-looking gap.

## 13. Glossary

| Term | Meaning |
|---|---|
| **Invitation** | A code (and shareable link) that grants accounts on one or more media servers, optionally limited by expiry, use count, access duration and libraries. |
| **Code** | The invitation's unique identifier typed or carried in the link; generated codes are twelve unambiguous characters. |
| **Use / use count / max uses** | One successful redemption; how many have happened; the cap, if any. "Used up" means the cap is reached. |
| **Access duration** | Number of days a member keeps access after redeeming; sets the member's expiry. |
| **Redemption / join** | The public flow in which an invitee turns a code into accounts. |
| **Reservation** | The atomic increment of the use count performed before any account is created. |
| **Identity** | One real person, who may hold several users across servers. |
| **User (member)** | One account of an identity on one media server. |
| **Orphaned / stale / matched** | Sync classifications: on the server only; locally only; both. |
| **Import** | Creating a local identity and user for an orphaned server account. |
| **Media server** | A connected Plex or Jellyfin instance. |
| **Provider** | The pluggable module for one server product, declaring its capabilities, permissions, sign-in style and join style. |
| **Library** | A content section on a server that an invitation may restrict access to. |
| **Capability** | Something a provider can do (create, delete, enable/disable, restrict libraries, set download permission). |
| **Permission** | A per-member switch on the server: download, stream, offline sync, transcode. |
| **Wizard** | A reusable sequence of steps with interactions shown to invitees. |
| **Pre-wizard / post-wizard** | A wizard run before account creation (completion enforced) or after it (cancellable). |
| **Step / interaction** | One page of a wizard; one required action on a step (click, timer, terms, text, quiz). |
| **Progress token / completion token** | Signed, short-lived proofs that steps were completed in order, and that a whole wizard was completed. |
| **Primary language / translation** | The language a step is authored in; alternative versions of its title and content. |
| **Home / shared / friend** | Plex relationship types: managed user in the owner's Plex Home; a Plex account with this server shared; a Plex friend without a share. |
| **Direct share** | Sharing a Plex server to an account without a friend request. |
| **PIN sign-in** | Plex's sign-in flow in which the user authorises a short code in a popup and the application polls for completion. |
| **Redemption token** | A one-time token exchanged server-side for the result of a PIN sign-in, so the raw provider token never reaches the browser. |
| **Admin** | A console user; separate from members. |
| **Bootstrap token** | The one-time token, printed in the log, required to create the first admin. |
| **Onboarding** | The persisted first-run step machine: account, security, server, complete. |
| **Trusted origin** | The public address browsers use; writes from any other origin are refused. |
| **Locked setting** | A console setting fixed by the operator's environment and therefore read-only in the UI. |
| **Session** | One admin sign-in, with a family of rotating refresh tokens, a hard fourteen-day limit and immediate revocation. |
| **Replay** | Reuse of a refresh token outside the lost-reply allowance; revokes that session. |
| **Circuit breaker** | Per-server protection that pauses automatic sync after repeated failures and probes again after a recovery period. |
| **Sync run** | The audit record of one library or user synchronisation. |
| **Dry run** | A user sync that reports differences without importing. |
| **Correlation id** | A random id attached to every error response and the matching log entries. |
