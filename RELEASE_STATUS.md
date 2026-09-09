# Release readiness — 0.6.0

This release moves broker startup settings into HA Configuration and removes
the separate settings server. Native amd64/aarch64 CI runs startup validation,
authentication, TLS/ACL, persistence and migration regressions, followed by
vulnerability scanning. CodeQL, workflow lint and secret checks remain required.

Before deployment, verify passing checks and take a cold backup. Verify an
existing installation's settings match the new HA configuration, then confirm
client reconnection and stored streams after the managed update. See RELEASING.md.
