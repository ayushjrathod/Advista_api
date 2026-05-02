FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PRISMA_BINARY_CACHE_DIR=/app

RUN apt-get update \
    && apt-get install -y build-essential openssl --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir .

COPY . .

# Generate Prisma client and fetch query engine binary into image
RUN python -m prisma generate && python -m prisma py fetch

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
