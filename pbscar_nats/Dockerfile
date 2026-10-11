# Build the exact official 2.15.1 source with patched Go 1.27.2. The upstream
# binary was built with Go 1.27.1 and contains fixed standard-library findings.
FROM golang:1.27.2-alpine@sha256:f92b6ef800e499660581efdabdf25d9d817a9d124eaf900924f0504e7e27e12d AS server
RUN apk upgrade --no-cache && apk add --no-cache git
ENV GOTOOLCHAIN=go1.27.2
WORKDIR /src
RUN git init . && git remote add origin https://github.com/nats-io/nats-server.git \
    && git fetch --depth 1 origin b2fd3efc7456b11b06a54877ad6f6ccfb911edb4 \
    && git checkout --detach FETCH_HEAD \
    && CGO_ENABLED=0 go build -trimpath -o /nats-server . \
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
