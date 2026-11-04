# Jellyfin: how it behaves, as the legacy app found it

From the previous app's spec, not re-verified. Each fact moves into `jellyfin-provider`'s spec,
which checks it against Jellyfin's latest stable release (D24), and this file is deleted once none
is left.

- The connection is the server's address plus an administrator API key; reading the system
  information tests it and gives the server's name and version.
- A user is created by name, and its password is set in a second call.
- Jellyfin stores no email for a user.
- A user can be deleted.
- Creating a name that already exists fails with an "already exists" reply.
- Library access is a policy set after the user exists: turning off "all libraries" and setting the
  list of enabled ones.
- Disabling a user sets the account's disabled policy flag; enabling clears it.
- The legacy app's permission switches, downloads, streaming, offline sync and transcoding, are
  Jellyfin user-policy flags.
- The user list holds every account, administrators included, without emails.
