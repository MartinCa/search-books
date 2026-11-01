ARG NODE_IMAGE=docker.io/library/node:26-slim@sha256:e4db4c914bf8ad241bd24804fc25d272d89bad97e68cdc8a1414862790a02c39
# The Python builder reuses the runtime image so the virtualenv copied between stages
# always matches its interpreter; uv itself is copied in as a standalone binary.
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0
ARG RUNTIME_IMAGE=docker.io/library/python:3.15.2-slim-trixie@sha256:c4158543ecb725b99e57d129dfd43d761d4c43e4577b5e23326aabb223cf7f4e

FROM ${NODE_IMAGE} AS frontend-builder
ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

# Node 26 no longer bundles Corepack, so install the pnpm release pinned in
# package.json's `packageManager` field directly.
RUN npm install --global "pnpm@$(node -p "require('./package.json').packageManager.split('@')[1].split('+')[0]")"

# --ignore-scripts: this stage only needs the packages on disk to run `pnpm
# build` below, never a package's own install script. Without it, lefthook's
# `prepare` script (`lefthook install`) shells out to `git rev-parse` to find
# the repo root - which fails outright here, since this image has no `git`
# binary and the build context never copies `.git` in the first place.
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --ignore-scripts

COPY index.html tsconfig.json tsconfig.app.json* vite.config.ts components.json ./
COPY src ./src
RUN pnpm build

FROM ${UV_IMAGE} AS uv

FROM ${RUNTIME_IMAGE} AS builder

COPY --from=uv /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependencies first: this layer stays cached until the lockfile changes.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

COPY app ./app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM ${RUNTIME_IMAGE}

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

RUN useradd --create-home --uid 10001 app

WORKDIR /app
COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=frontend-builder --chown=app:app /app/app/static/dist ./app/static/dist
COPY --chown=app:app app ./app

USER app
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python -c "import os,sys,urllib.request; sys.exit(0 if urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['PORT']}/healthz\", timeout=3).status == 200 else 1)"

CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8080}"]
