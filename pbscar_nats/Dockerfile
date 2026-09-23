FROM nats:2.15.0-alpine@sha256:ac8f88a6494bffc2c2a5289a0ca61cb28a9145c11ba5677cf24265d07f46d8d4 AS runtime
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
