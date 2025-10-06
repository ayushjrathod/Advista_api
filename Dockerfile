FROM python:3.12-slim

WORKDIR /code

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# Copy project files
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
RUN uv sync --frozen --no-dev

RUN useradd -m -u 1000 user
USER user
ENV PATH="/home/user/.local/bin:$PATH"

# Copy application code
COPY . /code

EXPOSE 8000

# Command to run the application
CMD ["sh", "-c", "uv run uvicorn main:app --host 0.0.0.0 --port $PORT --reload"]
