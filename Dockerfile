# Python 3.8 went end of life in October 2024 and buster with it, so the base
# image no longer received security fixes. It also capped the dependency set:
# requests 2.33+, which is where the current CVE fixes live, requires Python
# 3.10 or newer.
FROM python:3.13-slim-bookworm
LABEL org.opencontainers.image.authors="Alessio Caradossi <alkcxy@gmail.com>"

# Pinned rather than :latest so a rebuild of an old commit resolves the same
# uv, and so the binary matches the uv.lock format committed next to it.
COPY --from=ghcr.io/astral-sh/uv:0.12.5 /uv /uvx /usr/local/bin/

WORKDIR /usr/src/app

# .pyc written at build time instead of on every cold start, and copy rather
# than hardlink because the cache and the venv sit on different layers.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Dependencies first, so editing app.py does not invalidate the install layer.
# --locked fails the build if uv.lock is out of date with pyproject.toml
# rather than silently resolving something else.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

COPY . .

# The venv is put on PATH instead of wrapping the process in `uv run`. In a
# container the environment is already built and immutable, so `uv run` would
# only re-verify the lockfile on every start; putting .venv/bin first means a
# plain `python app.py` -- and any `docker run <image> python ...` such as the
# CI smoke tests -- resolves the installed interpreter with no indirection.
ENV PATH="/usr/src/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

CMD [ "python", "./app.py" ]
