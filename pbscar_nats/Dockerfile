# The official 2.15.1 release precedes its Docker tag. Verify release archives
# on both supported architectures and replace only the server executable.
FROM nats:2.15.0-alpine@sha256:ac8f88a6494bffc2c2a5289a0ca61cb28a9145c11ba5677cf24265d07f46d8d4 AS server
USER root
RUN case "$(uname -m)" in \
      x86_64) server_arch=amd64; server_sha=bf5edc7b1ce98e885c368cb43a886eb148dc5d0551d99f3cf6141fb5e1954c70 ;; \
      aarch64) server_arch=arm64; server_sha=e2fbab4cad7d3c76e3052eb959570393c9d73ba756b70bf8e9eea61e9ae6d49c ;; \
      *) exit 1 ;; \
    esac \
    && wget -q -O /tmp/server.tar.gz "https://github.com/nats-io/nats-server/releases/download/v2.15.1/nats-server-v2.15.1-linux-${server_arch}.tar.gz" \
    && printf '%s  /tmp/server.tar.gz\n' "$server_sha" | sha256sum -c - \
    && tar -xzf /tmp/server.tar.gz -C /tmp \
    && cp "/tmp/nats-server-v2.15.1-linux-${server_arch}/nats-server" /nats-server \
    && /nats-server --version

FROM nats:2.15.0-alpine@sha256:ac8f88a6494bffc2c2a5289a0ca61cb28a9145c11ba5677cf24265d07f46d8d4 AS runtime
COPY --from=server /nats-server /nats-server
USER root
RUN apk upgrade --no-cache && apk add --no-cache jq su-exec python3 openssl \
    && addgroup -S -g 10001 natsapp && adduser -S -D -H -u 10001 -G natsapp natsapp
ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.type="addon" io.hass.version="${BUILD_VERSION}" io.hass.arch="${BUILD_ARCH}"
COPY run.sh /run.sh
COPY server.py provision.py /opt/nats-console/
RUN chmod 755 /run.sh
ENTRYPOINT ["/run.sh"]

FROM runtime AS validation
RUN apk upgrade --no-cache && apk add --no-cache python3
COPY tests/provision.py /provision-test.py
RUN python3 /provision-test.py
COPY tests/runtime.py /runtime-test.py
COPY tests/console.py /console-test.py
COPY tests/unit.py /unit-test.py
RUN python3 /unit-test.py && python3 /runtime-test.py && python3 /console-test.py

FROM runtime AS final
COPY --from=validation /test-passed /usr/share/addon-runtime-tests.txt
