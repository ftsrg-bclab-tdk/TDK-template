ARG TEX_IMAGE=danteev/texlive:latest
FROM ${TEX_IMAGE}
# TEX_IMAGE is resolved from latest once by run.py. This build resolves current
# Python review dependencies once and records the installed versions in evidence.
RUN python3 -m pip install --no-cache-dir --only-binary=:all: --break-system-packages --root-user-action=ignore --upgrade pymupdf jsonschema
ENV PYTHONDONTWRITEBYTECODE=1
