# 0.6.0

- Move all broker startup settings into HA Configuration: authentication, user
  permissions, TLS, JetStream allowances and connection/message limits.
- Remove the duplicate settings UI and its HTTP listener.
- Remove snapshot restore mode; storage limits no longer double implicitly.
- Fail safely on differing legacy console settings until explicitly migrated;
  retire the old settings file after a matching successful start.
- Keep NUI and NATS clients responsible for permitted live administration.

# Changelog

## 0.5.2

- Enforce an administrator-configured HA identity allowlist for console reads and writes. Sidebar visibility alone does not authorize access. Existing installs must add trusted user IDs in Configuration, save and restart the app. Access-list changes require a restart; NATS continues running while the list is empty.
- Recover the exact deployed configuration and TLS bytes after a failed apply, even if the source certificate files have changed or disappeared.

## 0.5.1

- Make the non-root runtime check compatible with Home Assistant kernels that omit the optional process-children interface.

## 0.5.0

Add an administrator-only HA ingress settings console with certificate discovery, TLS and optional client certificate verification, per-user subject permissions, and storage/connection limits. Saved secrets remain hidden; settings are validated before applying. Existing token configuration remains compatible.

## 0.4.1

Apply Alpine security updates during builds, including patched OpenSSL libraries.

## 0.4.0

Update the pinned server to NATS 2.14.6. Validate restore-mode types and token size before startup. Expand negative authentication and file-permission checks.

## 0.3.0

- Community release candidate with pinned inputs and isolated image-build tests.
- Release, contributor, security and licensing guidance.
- Runtime privilege/readiness hardening and stronger release checks.


## 0.2.0

- Clearer Info page, setup documentation and troubleshooting guidance.
- Configuration field names and inline help for authentication and snapshot restores.
- Generic NATS server name and concise startup/error messages.
- Existing authentication, streams and storage limits are preserved.
