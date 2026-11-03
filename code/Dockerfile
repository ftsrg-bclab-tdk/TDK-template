# The runtime image: everything pinned, entry point `just`, so that
#   docker run --rm -v "$PWD/out:/out" ghcr.io/<you>/<repo>:v1.0.0 reproduce
# regenerates every result on any machine. Replace the base image and the install lines.
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl bash \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSfL https://just.systems/install.sh | bash -s -- --to /usr/local/bin
WORKDIR /work
COPY . .
# TODO install the toolchain and the dependencies, pinned
ENV OUT=/out
ENTRYPOINT ["just"]
CMD ["reproduce"]
