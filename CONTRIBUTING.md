# Contributing

Discuss substantial changes in an issue first. Keep app behavior independent of
any particular installation, workload or consumer. Never commit credentials,
backups, local options.json files or private deployment details.

Run `python tools/check_release.py` (requires PyYAML 6.0.3), `sh -n pbscar_nats/run.sh`,
and `docker build --build-arg BUILD_VERSION=test --build-arg BUILD_ARCH=amd64 -t addon-test ./pbscar_nats`.
The image build runs isolated runtime tests against disposable data; a failure
stops the build. CI also builds and tests natively on amd64 and arm64 runners.

For runtime changes, test in a disposable HA installation as well: configuration,
startup, shutdown, upgrade with existing data, backup/restore and reconnection.
Do not test destructive operations on a live broker. Document limits honestly.

Bump the app version for shipped changes, update its changelog and tests, and
preserve existing app identity and data paths. Pin updated upstream inputs and
review licenses. Contributions to wrapper code are accepted under LICENSE.

Before submitting, run `python tools/check_privacy.py` and Gitleaks on both the
working tree and Git history. Reports must redact matched credentials.
