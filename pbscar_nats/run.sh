#!/bin/sh
set -eu
umask 077
log() { printf '%s [%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2"; }
token=$(jq -er '.token | select(type == "string" and length >= 32 and length <= 1024)' /data/options.json 2>/dev/null) || {
  log ERROR "Authentication token is missing or too short. Set at least 32 characters in Configuration, save, and restart."
  exit 1
}
restore_mode=$(jq -er 'if has("restore_mode") then .restore_mode else false end | if type == "boolean" then tostring else error("type") end' /data/options.json 2>/dev/null) || {
  log ERROR "Invalid restore mode. Select a boolean value in Configuration."
  exit 1
}
mkdir -p /data/jetstream
file_budget=5GB
if [ "$restore_mode" = true ]; then
  file_budget=10GB
  log WARN "Snapshot restore mode is enabled (10 GiB). Disable it and restart after the restore."
fi
quoted_token=$(printf '%s' "$token" | jq -Rs .)
cat > /data/server.conf <<EOF
server_name: nats
listen: 0.0.0.0:4222
authorization { token: ${quoted_token} }
jetstream {
  store_dir: /data/jetstream
  max_file_store: ${file_budget}
  max_mem_store: 64MB
}
EOF
unset token quoted_token
log INFO "Checking NATS configuration. Token authentication enabled; JetStream persistence enabled."
if ! nats-server -t -c /data/server.conf; then
  log ERROR "NATS configuration validation failed. Review the preceding error and app configuration."
  exit 1
fi
log INFO "Starting NATS on client port 4222. File storage allowance: ${file_budget}; memory allowance: 64 MB."
chown natsapp:natsapp /data /data/server.conf
chown -R natsapp:natsapp /data/jetstream
chmod 700 /data /data/jetstream
chmod 600 /data/server.conf
exec su-exec natsapp nats-server -c /data/server.conf
