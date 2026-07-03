ARG PYTHON_VERSION=3.11


FROM python:${PYTHON_VERSION}-slim AS base

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /workspace


FROM base AS dev

# Install host tools available inside the container shell.
RUN apt-get update \
    && apt-get install -y --no-install-recommends git make \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user whose UID/GID match the host user so that volume-
# mounted files are not owned by root on the host side.
ARG USER_UID=1000
ARG USER_GID=1000
ARG DEV_USERNAME=dev
RUN groupadd --gid ${USER_GID} ${DEV_USERNAME} \
    && useradd --uid ${USER_UID} --gid ${USER_GID} --shell /bin/bash --create-home ${DEV_USERNAME} \
    && chown -R ${DEV_USERNAME}:${DEV_USERNAME} /workspace

USER ${DEV_USERNAME}
ENV PATH="/home/${DEV_USERNAME}/.local/bin:${PATH}"

# Pre-bake dependencies into the image layer so that day-to-day container
# starts are instant.  Source code is mounted at runtime, not copied here.
COPY --chown=${DEV_USERNAME}:${DEV_USERNAME} pyproject.toml uv.lock* ./
RUN --mount=type=cache,target=/home/${DEV_USERNAME}/.cache/uv,uid=${USER_UID},gid=${USER_GID} \
    uv sync --frozen --no-install-project --all-extras --all-groups
