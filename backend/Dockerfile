# The API image. Build context is `backend/`.
#
# Two stages. The builder installs the wheels into a virtualenv and the runtime
# copies just that venv across, so pip itself, its cache and every build
# artefact stay out of the shipped image. Nothing here needs a compiler:
# `psycopg[binary]`, `cryptography` and the rest all publish manylinux wheels
# for this Python, which is why there is no `apt-get build-essential` anywhere
# below and why the build is a minute rather than ten.

# --------------------------------------------------------------------------
# Stage 1: the wheels
# --------------------------------------------------------------------------
FROM python:3.12-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

# A virtualenv rather than the system site-packages, purely so the next stage
# can take the whole thing in one `COPY` and leave everything else behind.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /build

# Requirements alone first: this layer is the slow one, and it must not be
# rebuilt every time a line of app code changes.
COPY requirements-prod.txt ./
RUN pip install --no-cache-dir -r requirements-prod.txt

# --------------------------------------------------------------------------
# Stage 2: what actually ships
# --------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# Not root. A container that is compromised through this app should not also
# be able to rewrite the app: the code is owned by root and run by `saksham`,
# so the process can read it and cannot modify it. Created before the copy so
# the layer is cached.
RUN useradd --create-home --uid 10001 --shell /usr/sbin/nologin saksham

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY . /app

# `start.sh` is a shell script authored on a Windows machine, where git is
# configured with `core.autocrlf=true`. A CRLF at the end of the shebang line
# makes the kernel look for an interpreter called "/usr/bin/env sh\r", and the
# container dies at boot with "no such file or directory" naming a file that is
# plainly there. `.gitattributes` pins the checkout to LF; this strips them
# again at build time so the image is correct even from a checkout that is not.
RUN sed -i 's/\r$//' /app/start.sh && chmod +x /app/start.sh

# Render and most hosts hand the port in $PORT; 8008 is the local default.
ENV PORT=8008
EXPOSE 8008

# Whether this instance can actually serve a class, not merely whether a socket
# is open: `/health` reports schema readiness and how many migrations the
# database is behind. `python` rather than curl, which a slim image does not
# carry and which is not worth a layer.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD ["python", "-c", "import os,urllib.request;urllib.request.urlopen(f\"http://127.0.0.1:{os.environ.get('PORT','8008')}/health\",timeout=4)"]

USER saksham

CMD ["/app/start.sh"]
