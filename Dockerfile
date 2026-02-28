FROM python:3.13-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y build-essential --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Ensure pip and build tools are up-to-date
RUN pip install --upgrade pip setuptools wheel

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install the project and dependencies (editable mode for development)
RUN pip install --no-cache-dir -e .

# Copy the rest of the application
COPY . .

# Run Prisma generation only if the Prisma CLI is available in the image
RUN if command -v prisma >/dev/null 2>&1; then prisma generate; else echo "prisma CLI not found, skipping prisma generate"; fi

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
