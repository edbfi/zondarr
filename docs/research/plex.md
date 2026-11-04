# Plex: how it behaves, as the legacy app found it

From the previous app's spec, not re-verified. The Plex library audit (D18) checks these against the
pinned `@ctrl/plex` and Plex Media Server's latest public release (D24). Each fact moves into the
spec of the module that relies on it (`plex-provider`, `members`, `redemption`,
`owner-plex-sign-in`), and this file is deleted once none is left.

## Two systems

- Plex is two systems: the local server (its name, version, library sections and machine
  identifier) and Plex's account service (the owner's account, friends and home users, invitations,
  sharing, PIN sign-in and members' emails).
- The connection is the server's address plus the owner's Plex token. Plex can rate-limit requests;
  that is temporary.

## Members and relationships

- Sharing is keyed to a Plex account, so a username the invitee types can't receive a share.
- A Plex account relates to the owner's server in one of three ways:
  - **home:** a managed user inside the owner's Plex Home;
  - **shared:** a Plex account that has this server shared with it;
  - **friend:** a Plex friend with no share on this server.
- Plex can share a server directly to an account with chosen libraries, with no friend request for
  the invitee to accept. A friend invitation, by contrast, waits until the invitee accepts it, and a
  pending one is easy to miss.
- A member without an email can only be a managed home user.
- The user list holds friends and home users, each classed by whether this server is shared with
  them, and includes an email when Plex provides one.
- Directly shared members without a friendship may not appear in the friends list, so a later
  library or permission edit can fail with "user not found": edits work only for people in the
  owner's friends or home list.
- A share request that times out may still have been applied by Plex.

## What Plex can't do

- Plex has no disabled state for a member: access ends only by unsharing or removing them.
- Of the permissions, Plex supports only downloads, as "allow sync".
- Plex sets library access at share time, and a member uses their own Plex account, so there is no
  password at creation.

## Sign-in

- Plex signs users in with a PIN: the app asks Plex for a PIN, sends the user to Plex's sign-in page
  and checks the PIN until Plex reports success, after which it can read the user's token and email.
- Plex's PIN ids are sequential.
- Asking Plex for a PIN can fail transiently.
