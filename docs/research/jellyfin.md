# Jellyfin: how it behaves, as the legacy app found it

From the previous app's spec, not re-verified. The Jellyfin client decision (D19) checks these
against Jellyfin's latest stable release (D24). Each fact moves into `jellyfin-provider`'s spec, and
this file is deleted once none is left.

- The connection is the server's address plus an administrator API key; reading the system
  information tests it and gives the server's name and version.
- A user is created by name, and its password is set in a second call.
- Jellyfin stores no email for a user.
- Creating a name that already exists fails with an "already exists" reply.
- Library access is a policy: turning off "all libraries" and setting the list of enabled ones.
- Disabling a user sets the account's disabled policy flag; enabling clears it.
- The supported permissions are downloads, streaming, offline sync and transcoding.
- The user list holds every account, administrators included, without emails.
