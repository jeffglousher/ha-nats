# NATS for Home Assistant

A lightweight messaging server for connecting applications and services.

- Publish/subscribe and request/reply messaging with NATS.
- Persistent streams, replay and key/value storage with JetStream.
- Shared-token or individual-user authentication with subject permissions.
- Optional TLS using certificates from HA’s shared SSL folder.
- An admin settings console through Home Assistant ingress.
- Automatic startup, watchdog recovery and Home Assistant backups.

Set an authentication token in **Configuration**, then start the app.
Clients connect to `nats://HOME_ASSISTANT_HOST:4222` using that token.
Add your HA user ID under **Configuration → Console administrators**, save and restart the app, then open **Web UI** to discover certificates and configure access and capacity. The list starts empty; NATS runs normally while console access is disabled.
See [Documentation](pbscar_nats/DOCS.md) for setup, storage limits, backups and troubleshooting.

This app provides a NATS server. For browsing messages, streams and multiple saved server connections,
install NUI separately.

## Installation

On Home Assistant OS, open Settings → Apps → App store → Repositories and add
`https://github.com/jeffglousher/ha-nats`. Then install the app from this
repository and follow its documentation. Updates are managed by Home Assistant from this public repository.

Standalone Home Assistant Container installations do not include Supervisor apps.
These are independent community wrappers, not official upstream distributions.

See [Contributing](CONTRIBUTING.md), [Security](SECURITY.md),
[License](LICENSE), and [release readiness](RELEASE_STATUS.md).
