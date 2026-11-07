# Development scaffold. Resolve latest on each build and record its resulting identity.
ARG BASE_IMAGE=ubuntu:latest
FROM ${BASE_IMAGE}
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl bash git make python3 hyperfine \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSfL https://just.systems/install.sh | bash -s -- --to /usr/local/bin \
    && useradd --create-home --uid 10001 tdk
WORKDIR /work
COPY --chown=tdk:tdk . .
# The UID may be overridden when writing results to a host-owned mount.
RUN chmod -R a+rwX /work
ENV OUT=/out
USER tdk
ENTRYPOINT ["just"]
CMD ["--list"]
