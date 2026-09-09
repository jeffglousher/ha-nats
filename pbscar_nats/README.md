# NATS for Home Assistant

A lightweight messaging server for connecting applications and services.

- Publish/subscribe and request/reply messaging with NATS.
- Persistent streams, replay and key/value storage with JetStream.
- Token authentication for client connections.
- Automatic startup, watchdog recovery and Home Assistant backups.

Set an authentication token in **Configuration**, then start the app.
Clients connect to `nats://HOME_ASSISTANT_HOST:4222` using that token.
See **Documentation** for setup, storage limits, backups and troubleshooting.

This app provides a NATS server. For a browser-based management interface,
install NUI separately.
