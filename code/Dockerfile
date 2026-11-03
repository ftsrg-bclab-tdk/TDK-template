# The runtime image: everything pinned, entry point `just`, so that
#   mkdir -p out && docker run --rm --user "$(id -u):$(id -g)" -v "$PWD/out:/out" ghcr.io/<you>/<repo>:v1.0.0 reproduce
# regenerates every result on any machine. --user makes the files in out/ yours instead of root's;
# mkdir first, because a mount point Docker creates belongs to root. Replace the base image and the
# install lines.
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl bash hyperfine \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sSfL https://just.systems/install.sh | bash -s -- --to /usr/local/bin
WORKDIR /work
COPY . .
# TODO install the toolchain and the dependencies, pinned
# Recipes rebuild before they measure, so any --user must be able to write here.
RUN chmod -R a+rwX /work
ENV OUT=/out
ENTRYPOINT ["just"]
CMD ["reproduce"]
