ARG PYTHON_IMAGE=python:3.11-bookworm@sha256:970c99f886b839fc8829289040c1845dadaf2cae46b37acc7710333158ec29b4
FROM ${PYTHON_IMAGE}

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV XDG_RUNTIME_DIR=/tmp/runtime-root

WORKDIR /app

COPY pyproject.toml README.md /app/

RUN apt-get update \
    && apt-get install -y --no-install-recommends wkhtmltopdf \
    && mkdir -p /tmp/runtime-root \
    && chmod 700 /tmp/runtime-root \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

COPY . /app
RUN pip install --no-cache-dir -e ".[dev]"

CMD ["python", "main.py"]
