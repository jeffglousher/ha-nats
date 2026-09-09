# NATS

## Set up

1. In **Configuration**, choose shared-token authentication and enter a random
   token of 32–1024 characters, or select users and add individual NATS credentials.
2. Set storage allowances and any TLS options, save, then start the app.
3. Enable **Start on boot** and **Watchdog** on the Info page.
4. Connect NUI or your application to `nats://HOME_ASSISTANT_HOST:4222` using
   the configured credentials. The Network section controls the host port.

**HA Configuration is the only source of broker startup settings.** Save and
restart to apply changes, including renewed certificates. Clients must reconnect.
There is no separate NATS settings web page. Install the separate
[NUI app](https://github.com/jeffglousher/ha-nats-nui) for live administration.

## Access and live administration

Shared-token mode gives every token holder the same unrestricted NATS access.
For different access levels, use individual users with explicit publish and
subscribe subject lists. Empty lists deny that operation; `*` matches one subject
segment and `>` matches the remaining segments at the end. Passwords must be
16–1024 characters. Do not leave a password blank to preserve an earlier value:
HA Configuration contains the complete configuration.

NUI and applications can publish and subscribe, create and configure streams,
manage consumers and administer key/value data when their NATS permissions allow
it. JetStream administration uses `$JS.API.>` requests and reply inboxes;
grant only the API subjects and reply subscriptions needed by each application.
For an unrestricted administrator, allow `>` for both publish and subscribe.
Do not give those permissions to a read-only consumer.

HA users and NATS users are separate identities. NUI's HA access allowlist grants
access to its shared console; the credentials saved in each NUI connection control
broker permissions. Do not treat one shared NUI installation as per-HA-user NATS
isolation. Broker credentials, server-wide capacity and TLS are startup settings,
not settings that NUI's stream API changes.

## TLS

Place a certificate chain and matching private key in HA's shared `/ssl` folder.
Set their filenames in Configuration and enable TLS. Clients must trust the CA
and connect using a hostname in the certificate. The app validates the pair,
expiry and path containment and uses TLS 1.2 or newer.

Optional client certificate verification also requires a client CA filename;
clients still need NATS credentials. HA Cloud access does not populate `/ssl` or
provide TLS for the NATS TCP listener. Certificate renewal takes effect on restart.
The SSL mount is read-only. Include source certificates in your backup plan.

## Storage and resource limits

Defaults are **5 GiB JetStream file storage**, **64 MiB memory-backed storage**,
**1024 connections** and **1024 KiB per message**. Configure these explicitly in
HA. The file allowance is a logical JetStream limit, not a filesystem quota for
all files, logs or backups; the memory allowance is not a total process RAM cap.
HA apps share host resources, so retain free space for HA and other apps.

Streams with an explicit maximum byte size reserve that allowance from the broker budget, even when they currently hold little data. If the sum of file-stream limits consumes the entire file allowance, NATS rejects new file streams and buckets with "insufficient storage resources available". Compare the sum of configured stream limits with the broker allowance, and explicitly adjust one of those limits to leave headroom. Free host disk alone does not resolve this error.

Applications create their own streams and retention policies. Set stream size
and age limits for each workload. At a limit, publishing can fail or older
messages can be discarded according to the stream policy. Lowering the broker
allowance below existing usage can prevent normal operation.

There is no automatic storage-limit expansion during restores. If a restore
needs more capacity, explicitly raise the file allowance and restart, perform
the restore, then return to an allowance that fits the resulting data.

## Updating and restoring

Updates and restarts preserve JetStream data. Take a cold app backup before
configuration changes and restore the full app backup to recover settings and
data together. Uninstalling can remove app data.

When upgrading from 0.5.x, copy settings from the old console into HA Configuration.
The first start compares any saved console settings with HA's startup settings.
If they differ, startup stops without changing stored messages or discarding the
old settings. Use the prior version's console or a private backup to recover the
values; never post a configuration containing credentials in an issue. Once they
match and the broker starts, the old settings file is removed. The retired
snapshot restore and console-administrator options have no effect.

## Logs and troubleshooting

- **Startup configuration error:** check authentication mode, required passwords,
  numeric ranges and certificate filenames in Configuration.
- **Previous console settings differ:** complete the migration described above.
- **Authentication error:** check the NATS connection credentials and auth mode.
- **Permissions violation:** check publish, subscribe, JetStream API and reply subjects.
- **TLS failure:** check CA trust, hostname, certificate expiry and matching key.
- **Connection refused:** check app state and the Network port mapping.
- **Storage limit:** inspect stream retention and free HA disk space.

Logs use standard app output; message tracing is disabled. For support include
the app version, platform and sanitized errors, never credentials or message data.
