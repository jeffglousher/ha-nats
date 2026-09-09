# NATS

## Quick start

1. Open **Configuration** and enter a unique, randomly generated authentication
   token of at least 32 characters. A password manager can generate one.
2. Leave **Snapshot restore mode** off and save.
3. Start the app. Enable **Start on boot** and **Watchdog** on the Info page.
4. Connect your NATS client to `nats://HOME_ASSISTANT_HOST:4222`. Supply the
   token in the client's token field, separately from the server URL.

Replace `HOME_ASSISTANT_HOST` with your Home Assistant hostname or IP address.
If you change the client port under **Network**, use that port in the URL.
The log reports when the server is ready to accept connections.

## Configuration

### Authentication token

Required. Every client must supply the same token. The field is masked in the
configuration form; the startup script never prints it. Keep the token out of
screenshots, shared configuration files and support requests.

To rotate it, save a new token and restart the app, then update every client.
Existing clients will need the new token to reconnect. This app uses one shared
credential with access to all subjects and streams; per-user permissions are
not configured by this app.

### Snapshot restore mode

Default: off. Enable only while restoring a large JetStream snapshot.
It temporarily raises the server file-storage allowance from 5 GiB to 10 GiB
to accommodate restore staging. It does not change individual stream limits.
Ensure the host has enough free space first. Disable it and restart after the
restore, before resuming publishers. This is not an everyday capacity setting.

### Network

**NATS client connections** defaults to TCP port 4222. This is the only exposed
port. The app does not provide a web page, monitoring endpoint, cluster port,
TLS listener or WebSocket listener. Use trusted networks; do not forward this
unencrypted client port to the internet.

## Storage and retention

JetStream is enabled and stores data in the app's persistent data volume.
Normal limits are **5 GiB file storage** and **64 MiB memory storage**.
Applications create their own streams, subjects, consumers and retention rules.
The server does not create them automatically.

When a stream or server limit is reached, publication can fail or older data
can be removed, depending on the stream's discard policy. Set retention and
capacity deliberately, monitor usage, and keep free space on the HA host.
Restarting or updating the app preserves stored data. Uninstalling can remove it.

## Backups and recovery

Include this app in Home Assistant backups. Backups are **cold**: HA briefly
stops the app, copies its data and starts it again. Plan for a short interruption
and configure clients to reconnect. Backups contain credentials and stored messages.

For full-app recovery, restore the Home Assistant app backup. For a portable
JetStream migration, use NATS snapshot/restore tools: pause publishers, back up
streams and consumer state, restore, then verify message counts, sequence numbers
and consumers before resuming. Keep the original backup until verification passes.

## Logs and troubleshooting

Open the app's **Log** tab. Startup messages summarize authentication, storage
mode and configuration validation, followed by standard NATS server logs.
Debug and message tracing are disabled; message payloads are not traced.

- **Authentication token is missing or too short:** enter at least 32 characters
  in Configuration, save, and restart.
- **Authorization violation:** check the client's token. After rotation, update
  all clients. Do not put the token in a URL.
- **Connection refused or timed out:** confirm the app is running, the hostname
  and Network port are correct, and the client can reach the HA host.
- **Storage limit or insufficient space:** inspect stream retention and HA disk
  usage. Snapshot restore mode is only for temporary restore staging.
- **Repeated restarts:** read the error immediately before the shutdown. Check
  configuration and disk space; disabling the watchdog does not fix the cause.

For support, include the app version, HA installation type, relevant error lines
and reproduction steps. Remove credentials and private subject or message data.

## Learn more

- [NATS documentation](https://docs.nats.io/)
- [JetStream](https://docs.nats.io/nats-concepts/jetstream)
- [Report an app issue](https://github.com/jeffglousher/ha-nats/issues)

Authentication tokens must contain 32–1024 characters. Invalid option types fail
startup before the broker starts. The generated credential configuration is mode
0600 and JetStream storage is mode 0700. Tokens grant broker-wide access; use a
trusted network and protect backups containing configuration.
