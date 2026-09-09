# NATS

## First start

1. In **Configuration**, enter a unique random token of 32–1024 characters.
2. Leave **Snapshot restore mode** off, save and start the app.
3. Enable **Start on boot** and **Watchdog** on the Info page.
4. In **Configuration → Console administrators**, add your HA user ID (32 lowercase hexadecimal characters, shown on your HA user details page), save and restart the app, then open **Web UI** to configure encryption, access and capacity.

Only listed HA identities may read or change console settings. An empty list
keeps NATS running but denies console access. HA administrators manage this list
in Configuration; the console cannot grant access. **Save and restart the app**
after changing this list: Supervisor refreshes the runtime options file on startup.
Until that restart, the previous list remains active, including removed identities. The sidebar administrator setting alone is not
an authorization boundary. Only select trusted identities, and remove them here
when access should end (changing their HA role does not change this explicit list).

Existing installations retain their token, port and JetStream data on upgrade.
TLS is initially off. Clients connect to `nats://HOME_ASSISTANT_HOST:4222`,
with the token supplied separately from the URL. Use the port selected under
**Network** if you changed it.

## Settings and discovery

The console shows broker status, the active encryption setting and available
certificate filenames. **Refresh discovery** rechecks these without restarting
NATS; it asks before discarding unsaved edits. TLS, user permissions and advanced
limits appear progressively as you select them. Certificate contents, private
keys and saved passwords are never returned to the browser.

After the first successful **Apply settings**, the console's settings become
authoritative, including credentials. The token in HA's Configuration tab is
only the initial bootstrap value; changing it then has no effect. Use Web UI to
rotate the active token or user passwords. Blank secret fields preserve saved
values. A renamed or new user requires a new password.

Applying validates the configuration and restarts NATS briefly. Invalid input
leaves the running broker alone. A failed restart or save attempts to restore
the exact previously deployed configuration and certificate bytes; check Logs if recovery fails. Renewing or removing source files in `/ssl` does not change the rollback copy. Clients must reconnect.
Keep an app backup before changing access or encryption.

## Local TLS using the HA certificate

The app mounts HA's shared `/ssl` folder read-only. Choose the certificate chain
and matching private-key filenames there, commonly `fullchain.pem` and
`privkey.pem`. A certificate used by a separate reverse proxy is not necessarily
present in that folder. An empty discovery list means no files are available;
the app does not obtain or issue certificates.

Enable **Encrypt client connections with TLS**, select the pair and apply.
The app checks that the files stay inside `/ssl`, the pair loads and the leaf
certificate has not expired. Clients still must verify the issuing CA and the
hostname: connect using a hostname listed in the certificate, for example
`tls://nats.example.net:4222`. An IP address requires a matching IP certificate
SAN. Follow your client's TLS settings if it does not use a `tls://` URL.
Do not turn off hostname or CA verification to make a connection work.

TLS 1.2 or newer is required. NATS sends its initial protocol INFO before the
TLS handshake; credentials and subsequent traffic follow the encrypted handshake.
TLS is required for every client once enabled; there is no second plaintext port.
After certificate renewal, **restart the app or apply settings again** to load
the replacement files. Automatic certificate reload is not implemented.

Under **Require client certificates**, select a client CA to require a trusted
certificate from every client as well as the configured token or user/password.
Configure all clients first. This is optional mutual TLS, not a replacement for
NATS subject permissions. HA ingress protects the settings page separately;
it does not encrypt NATS client traffic.

## Authentication and subject permissions

- **Shared token:** one credential grants full access to all subjects and streams.
- **Individual users:** each client has a username, a 16–1024 character password,
  and separate publish and subscribe allow lists. Empty lists deny that operation.
  Up to 64 users and 128 subjects per permission list are supported.

Enter one subject per line. `sensors.*` matches one segment; `sensors.>` matches
one or more trailing segments. `>` grants unrestricted access for that operation.
Switching between modes replaces the active authentication method; it does not
accept both at once. Use separate credentials for independently managed clients.

Request/reply clients also need permissions for their request subjects and reply
inboxes. JetStream clients use `$JS.API.>` and reply subjects such as `_INBOX.>`;
consumer delivery and acknowledgement subjects depend on their configuration.
Grant only the subjects your application needs. The console does not infer
permissions from traffic or silently broaden a denied operation.

Use NUI's **ALL → NEW** to save multiple server connections. Give each connection
its own URL and credentials; HA login and NATS authentication are separate.
Update saved connections after changing this server's authentication or TLS.

## Capacity, storage and network

Default JetStream allowances are **5 GiB file storage** and **64 MiB memory**.
The console supports 1–1024 GiB file storage, 16–4096 MiB memory, 1–65536 client
connections (default 1024), and 1–8192 KiB message size (default 1024).
These limits do not reserve host resources. Keep room for HA, backups and other
apps. Existing streams must fit any reduced limit. Applications create their own
streams, consumers and retention rules; the app does not create them automatically.

At a stream limit, publishing can fail or old data can be discarded according to
its policy. Restarting and updating preserve stored data; uninstalling can remove it.
**Snapshot restore mode** in HA Configuration temporarily doubles the configured
file allowance (5 to 10 GiB by default). Enable only for restore staging, then
disable and restart before resuming publishers. It does not change stream limits.

TCP 4222 is the only exposed port. The settings console is available only through
HA ingress with an explicit HA identity allowlist, with no direct LAN port. This app does not configure clustering,
leaf nodes, WebSockets, a monitoring port, accounts or JWT/NKey authentication.
Keep the broker on your intended local network; it does not configure a firewall.

## Backups and recovery

Include this app in Home Assistant backups. Backups are cold: HA briefly stops the
app, copies data and restarts it. They contain console settings, credentials and
stored messages; protect them accordingly. Include HA's SSL folder separately
in your backup plan, since the app's read-only mount is not its own data volume.

Restore the full app backup to recover settings and data together. For portable
JetStream snapshots, pause publishers, back up streams and consumers, restore,
then verify counts, sequence numbers and consumers before resuming. Keep the
original backup until verification passes.

## Logs and troubleshooting

Open **Logs** for startup validation and standard NATS messages. Debug and message
tracing stay disabled; the console does not print credentials or submitted settings.
NATS errors may contain usernames and subject names; redact private information
before sharing logs.

- **Missing initial token:** enter 32–1024 characters in Configuration and restart.
- **Authorization violation:** check the active access mode and client credentials.
- **Permissions violation:** check the user's publish, subscribe and reply subjects.
- **Certificate validation failed:** check filenames, expiry and matching key.
  Restore the certificate files if TLS prevents startup, then restart.
- **TLS client error:** check CA trust, hostname and optional client certificate.
- **Connection refused:** check app status, hostname and the configured Network port.
- **Storage limit:** inspect stream retention and free HA disk space.
- **Apply failure/repeated restarts:** check the error before shutdown and available
  disk space. Restore the last app backup if settings cannot be recovered.

For support include app version, HA installation type, sanitized error lines and
reproduction steps. Never attach credentials or private message data.

## Learn more

- [NATS documentation](https://docs.nats.io/)
- [TLS](https://docs.nats.io/running-a-nats-service/configuration/securing_nats/tls)
- [Subject authorization](https://docs.nats.io/running-a-nats-service/configuration/securing_nats/authorization)
- [Report an app issue](https://github.com/jeffglousher/ha-nats/issues)
