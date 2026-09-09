# NATS for Home Assistant

A lightweight messaging server for connecting applications and services.

- Publish/subscribe and request/reply messaging with NATS.
- Persistent streams, replay and key/value storage with JetStream.
- Token authentication for client connections.
- Automatic startup, watchdog recovery and Home Assistant backups.

Set an authentication token in **Configuration**, then start the app.
Clients connect to `nats://HOME_ASSISTANT_HOST:4222` using that token.
See [Documentation](pbscar_nats/DOCS.md) for setup, storage limits, backups and troubleshooting.

This app provides a NATS server. For a browser-based management interface,
install NUI separately.

## Installation

On Home Assistant OS, open Settings → Apps → App store → Repositories and add
`https://github.com/jeffglousher/ha-nats`. Then install the app from this
repository and follow its documentation. Repository installation becomes
available when this repository is public; this candidate is not yet published.

Standalone Home Assistant Container installations do not include Supervisor apps.
These are independent community wrappers, not official upstream distributions.

See [Contributing](CONTRIBUTING.md), [Security](SECURITY.md),
[License](LICENSE), and [release readiness](RELEASE_STATUS.md).
