#!/bin/sh
set -eu
umask 077
exec python3 /opt/nats-console/server.py
