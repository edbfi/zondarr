# Temporary Renovate repair canary

This isolated package exercises the shared automation v2 App publisher without
changing the application dependencies. Renovate upgrades the exact Biome pin
using the existing release-age and automerge policy. The repair must migrate the
configuration, publish through the scoped App, pass full CI on the repaired head,
and receive a genuine Renovate merge request before checked merging.

The integration job installs this lockfile frozen and treats configuration
warnings as failures. Remove this directory, its integration step, and the
`canary` repair job after the unattended merge and subsequent scan/rebase checks.
