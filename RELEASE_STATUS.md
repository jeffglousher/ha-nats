# Release readiness — 0.4.0 candidate

## Verified

- Release metadata, translations, pinned build inputs and minimal privileges.
- Native amd64 image build and isolated runtime regression tests.
- Authentication, persistence, restart recovery and secret-safe service logging.
- NATS 2.14.6 with invalid authentication/options rejected, non-root execution,
  restricted credential/storage permissions and JetStream retention after restart.

## Remaining release gates

- Native arm64 image builds and full container operating-system vulnerability scan.
- Fresh repository installation and cold backup/restore on a disposable HA system.
- Final license/attribution review and release evidence for supported platforms.

Source publication is separate from declaring a stable supported release. See
RELEASING.md for the complete release checklist.
