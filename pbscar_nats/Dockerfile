FROM nats:2.14.6-alpine@sha256:ad7a43eb7e3337c3c38ce5d784d1461791f95f730f252d2b25eee699752a0ca3 AS runtime
USER root
RUN apk add --no-cache jq su-exec \
    && addgroup -S -g 10001 natsapp && adduser -S -D -H -u 10001 -G natsapp natsapp
ARG BUILD_VERSION
ARG BUILD_ARCH
LABEL io.hass.type="addon" io.hass.version="${BUILD_VERSION}" io.hass.arch="${BUILD_ARCH}"
COPY run.sh /run.sh
RUN chmod 755 /run.sh
ENTRYPOINT ["/run.sh"]

FROM runtime AS validation
RUN apk add --no-cache python3
COPY tests/runtime.py /runtime-test.py
RUN python3 /runtime-test.py

FROM runtime AS final
COPY --from=validation /test-passed /usr/share/addon-runtime-tests.txt
