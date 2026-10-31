# Implementation plan: `secrets`

## Overview

Build module 1 of the capability map as [docs/SPEC-secrets.md](../docs/SPEC-secrets.md) specifies
by copying obzorarr's built `secrets` at `b9b4737` (obzorarr #283), the reference app for this
shared area (AGENTS.md, Shared groundwork), in one PR: `feat(secrets): encrypt stored secrets,
ported from obzorarr`, on the branch `feat/secrets`. The tasks are in [todo.md](todo.md).

## Architecture decisions

- **Copy, don't rebuild.** The design, the code and the tests are obzorarr's, already reviewed and
  built. The copy changes only the app's name, so the two apps can't drift; a real bug found during
  the port is fixed in obzorarr first, in its own PR, then ported.
- **One PR, two commits.** `feat(secrets): port obzorarr's secrets code and tests`, then
  `docs(secrets): close the secrets work stream`. Splitting the library from its wiring wouldn't
  shrink the review and would leave unwired code on `main`.
- **The copy is proved, not trusted.** Each copied path is diffed against obzorarr's after the
  renames, and the PR body carries the command and its output.

## Risks

- **A leak test trips on the renamed name.** A temp-folder prefix holding the app's name may share
  6 characters with the text a leak test checks; then the prefix drops the app's name, and the PR
  body declares it.
