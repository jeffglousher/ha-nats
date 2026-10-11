# Release readiness: 0.6.2

The container builds official NATS Server 2.15.1 with Go 1.27.2. Startup settings
come from Home Assistant Configuration. Existing JetStream data stays in the
add-on's persistent data directory across managed updates.

The image checks cover startup, authentication, TLS and subject permissions,
persistence, configuration validation and vulnerability scanning on amd64 and
aarch64. Workflow lint, secret checks and CodeQL also run in this repository.

Before deployment, verify the current image checks and take a scoped backup.
After the managed update, confirm the server version, client reconnection,
configured subjects, retained streams and consumer counts. Follow RELEASING.md.
