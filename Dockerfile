ARG PYTHON_IMAGE=python:3.11-bookworm@sha256:970c99f886b839fc8829289040c1845dadaf2cae46b37acc7710333158ec29b4
ARG TIPPECANOE_VERSION=2.79.0

FROM ${PYTHON_IMAGE} AS tippecanoe-build

ARG TIPPECANOE_VERSION

RUN apt-get update \
    && apt-get install -y --no-install-recommends git gcc g++ make libsqlite3-dev zlib1g-dev \
    && git clone --depth 1 --branch "${TIPPECANOE_VERSION}" https://github.com/felt/tippecanoe.git /src/tippecanoe \
    && make -C /src/tippecanoe -j2 \
    && install -m 0755 /src/tippecanoe/tippecanoe /usr/local/bin/tippecanoe \
    && rm -rf /var/lib/apt/lists/*

FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV XDG_RUNTIME_DIR=/tmp/runtime-root
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PROJECT_ENVIRONMENT=/opt/docmap-venv
ENV PATH="/opt/docmap-venv/bin:$PATH"

WORKDIR /app

COPY pyproject.toml uv.lock README.md /app/

RUN apt-get update \
    && apt-get install -y --no-install-recommends libsqlite3-0 wkhtmltopdf \
    && mkdir -p /tmp/runtime-root \
    && chmod 700 /tmp/runtime-root \
    && rm -rf /var/lib/apt/lists/*

COPY --from=tippecanoe-build /usr/local/bin/tippecanoe /usr/local/bin/tippecanoe

RUN pip install --no-cache-dir uv==0.11.28 \
    && uv sync --frozen --no-dev --no-install-project

COPY . /app
RUN uv sync --frozen --no-dev

CMD ["python", "main.py"]
