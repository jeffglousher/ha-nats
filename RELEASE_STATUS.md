# Release readiness — 0.5.1

## Verified

- Native amd64 and aarch64 image builds and runtime regression tests.
- HIGH/CRITICAL container vulnerability scans, CodeQL, workflow lint and secret scans.
- Existing token authentication, non-root broker execution and JetStream persistence.
- TLS trust and hostname rejection, user authentication and denied subject permissions.
- Ingress peer validation, secret redaction, atomic writes and failed-apply recovery.
- Settings interface checked in a browser at desktop and phone widths.
- Repository-managed 0.4.1 installation and cold backup/restore migration on HA.

## Deployment checks

For each release, verify repository-managed update, existing client reconnects,
persistent streams and authenticated ingress on HA. TLS activation also requires
an available certificate and matching client hostname; source support alone does
not establish encrypted deployment. Certificate renewal requires an app restart.

See RELEASING.md for the release checklist and THIRD_PARTY.md for attribution.
