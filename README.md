# Advista API

FastAPI backend for Advista — a competitive intelligence and ad research assistant. It orchestrates chat-driven brief collection, multi-source research gathering, and AI-synthesized report generation.

---

## What is this project?

Advista_api is the backend half of the Advista product — a competitive intelligence tool that helps users understand how competitors are advertising and positioning themselves.

A user opens the client, answers a conversational intake chatbot that builds a structured research brief, then triggers a research run. This API handles everything from that point. It accepts and authenticates the request using Firebase token verification and Postgres user sync. It manages the conversational brief collection over streaming SSE, asking clarifying questions and tracking which fields of the brief are complete. Once the brief is ready, it generates targeted search queries, collects source material from SerpAPI across web, news, Google Ads, and shopping results, extracts YouTube transcripts from relevant videos, processes and scores the collected sources, and synthesizes a structured competitive intelligence report using a LangGraph agent backed by Groq. All users, sessions, and reports are persisted in Postgres via Prisma.

In short: the client collects the user's intent and renders the experience. This API does the orchestration, data collection, storage, and report generation.

---

## Purpose

Advista was built to demonstrate an end-to-end AI product with real infrastructure concerns: authenticated multi-user access, conversational state management, multi-source data ingestion, LLM-backed synthesis, persistent storage, and a deployment path that supports both long-lived servers with Celery workers and ephemeral Lambda containers via Mangum.

It is not a toy. It has a real frontend, a real database schema, Firebase auth integration, and two deployment modes wired up.

---

## Tech Stack

The service is written in Python 3.13+. The API framework is FastAPI with Uvicorn. Streaming uses SSE via `sse-starlette`. The database ORM is Prisma Client Python targeting PostgreSQL. Authentication is handled by the Firebase Admin SDK, which verifies ID tokens sent by the browser client and syncs Firebase identities into the local Postgres user table. LLM orchestration is done with LangChain and LangGraph. The LLM backend is Groq running `llama-3.3-70b-versatile`. Research source collection uses SerpAPI for web, news, and ads data and the YouTube Transcript API for video content. Background job processing is available via Celery with Redis, but both are optional — when disabled, the research pipeline runs inline in an async task compatible with Lambda's execution model. Lambda deployment is handled by Mangum, which adapts the FastAPI ASGI app to the Lambda event format. Dependencies are managed with `uv` and configuration uses `pydantic-settings` with a `.env` file.

---

## Architecture

### The request flow

Every interaction flows through three major phases.

The first phase is the chat phase, handled by `chatbot_service` with a LangGraph state graph. The chatbot streams responses over SSE, asking questions to collect the fields needed to build a complete research brief. At any point the client can request the current brief state, the completion percentage, and a list of missing fields.

The second phase is the research phase, triggered when the brief is complete. The `research_service` uses an LLM call to generate targeted search queries from the brief. The `serpapi_service` then fans out to multiple SerpAPI engines in parallel and the `youtube_service` extracts transcripts from relevant videos. The `analysis_service` normalizes and scores the collected source material.

The third phase is synthesis. The `synthesis_service` runs a LangGraph agent that assembles the processed sources and generates a structured competitive intelligence report. The completed report is persisted to Postgres via Prisma through the `research_session_repository`.

### Two deployment modes

The API supports two runtime modes controlled by environment variables.

In long-lived server mode, Docker and optional Celery are used. Research runs can be dispatched to a Celery worker queue backed by Redis. The main API handles HTTP and SSE while the worker handles the slow research pipeline work asynchronously.

In ephemeral Lambda container mode, when `ENABLE_CELERY=false`, research runs inline in an async task compatible with the Lambda cold-start and timeout model. `lambda_handler.py` adapts the FastAPI ASGI app to the Lambda event format via Mangum. The container binds quickly to `0.0.0.0:$PORT` and starts even if the database is temporarily unavailable, reporting DB state via `/health` instead of failing container startup.

---

## Project Layout

The root contains `main.py` as the FastAPI app factory handling CORS setup and route registration, and `lambda_handler.py` as the AWS Lambda entrypoint. The `prisma/` directory holds `schema.prisma` defining the User, ChatSession, and ResearchSession tables.

Inside `src/`, the `controllers/` directory has the HTTP route layer split into `auth_controller.py`, `chat_controller.py`, and `research_controller.py`. The `services/` directory is where the business logic lives: `auth_service.py` handles token validation and user sync, `firebase_service.py` wraps the Firebase Admin SDK, `chatbot_service.py` drives the LangGraph brief-collection conversation, `research_service.py` generates search queries from a completed brief, `serpapi_service.py` orchestrates multi-engine search collection, the `serpapi_clients/` subdirectory holds smaller focused clients for specific SerpAPI engines, `youtube_service.py` handles transcript extraction, `analysis_service.py` normalizes and scores source material, `synthesis_service.py` runs the LangGraph report synthesis agent, and `research_session_service.py` manages session lifecycle. The `repositories/` directory has Prisma-backed persistence helpers. The `models/` directory holds Pydantic request and response models. The `utils/` directory has `config.py` for settings and environment loading.

The `worker/` directory has `celery_app.py` defining the Celery application and `tasks.py` with the background research task. The `scripts/` directory holds `build-and-push-lambda.sh` for ECR build and push. Two Dockerfiles exist: `Dockerfile` for the standard long-lived server image and `Dockerfile.lambda` for the Lambda container image. `docker-compose.yml` wires together the API, Redis, and Celery worker.

---

## API Reference

### Auth routes under `/api/v1/auth`

`GET /me` returns the current auth state if a valid Firebase bearer token is present. `GET /check-email-unique` checks whether an email is already registered. `POST /logout` is a client-side logout acknowledgment — Firebase handles actual auth state in the browser.

Legacy email and password signup endpoints still exist in the codebase but intentionally return 410 Gone. Firebase client auth is the source of truth for all identity operations.

### Chat routes under `/api/v1/chat`

`GET` or `POST /initialize-thread` creates a new chat thread. `POST /stream` streams the chatbot response as Server-Sent Events. `GET /research-brief/{thread_id}` returns the current brief object, its completion percentage, and a list of missing required fields.

### Research routes under `/api/v1/research`

`POST /start-research` runs the full research pipeline from a completed brief. `GET /sessions` returns the saved research history for the currently authenticated user. `GET /report` fetches a completed report by `session_id`. `GET /processed-results` is a local debug endpoint backed by a file rather than the database.

---

## Setup

### Prerequisites

You need Python 3.13 or newer, `uv` for dependency management, a running PostgreSQL instance, a Firebase project for authentication, a SerpAPI key, at least one Groq API key, and Redis only if you want Celery workers locally.

### Install dependencies

```bash
uv sync
```

### Configure environment

Create `.env` in `Advista_api/`:

```env
ENVIRONMENT=development
PORT=8000

DATABASE_URL=postgresql://USER:PASSWORD@HOST:5432/DB_NAME
DIRECT_URL=postgresql://USER:PASSWORD@HOST:5432/DB_NAME

SECRET_KEY=replace-me
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60

FIREBASE_PROJECT_ID=
FIREBASE_PRIVATE_KEY_ID=
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=
FIREBASE_CLIENT_ID=

GROQ_MODEL=llama-3.3-70b-versatile
GROQ_API_KEY1=
GROQ_API_KEY2=
GROQ_API_KEY3=
GROQ_API_KEY4=
GROQ_API_KEY5=

SERPAPI_API_KEY=

ENABLE_CELERY=false
ENABLE_REDIS=false
```

Multiple `GROQ_API_KEY*` entries enable key rotation to work around Groq rate limits during heavy synthesis runs. Optional mail settings and debug file output settings can also be added — see `.env.example` for the full list.

### Generate the Prisma client and apply the schema

```bash
uv run prisma generate
uv run prisma migrate deploy   # production / first run
# or
uv run prisma db push          # local schema iteration
```

### Start the API

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The app is available at `http://localhost:8000` and the health check at `http://localhost:8000/health`.

### Running with Celery workers

Set `ENABLE_CELERY=true` and `ENABLE_REDIS=true` in `.env`, then:

```bash
docker compose up --build
```

This starts the API on port 8000, Redis on 6379, and a Celery worker.

---

## Deployment

### AWS Lambda (containerized)

```bash
./scripts/build-and-push-lambda.sh
./scripts/build-and-push-lambda.sh personal
./scripts/build-and-push-lambda.sh --no-cache
```

The Lambda handler is `lambda_handler.handler`. The image targets `linux/amd64` for Lambda compatibility and pushes to ECR.

### Standard container

For long-lived environments, `Dockerfile` and `docker-compose.yml` run the API with optional Redis and Celery.

---

## Design Tradeoffs

### LangChain and LangGraph over a raw SDK

This project uses LangChain and LangGraph, which is the opposite choice from ValueX (also in this repo). The reasons are different here. The chatbot brief-collection flow benefits from LangGraph's state graph model — it needs to maintain conversational state across multiple turns, track which brief fields are filled, decide when to prompt for missing information, and signal completion. This is exactly the kind of stateful, branching control flow LangGraph is designed for. The synthesis agent similarly benefits from LangChain's tool integration and chain composition for assembling and processing research results from multiple sources.

The tradeoff is that LangGraph adds abstraction and debugging complexity compared to a hand-rolled loop. When something goes wrong inside a graph node, the stack trace is harder to read than a plain function call.

### Firebase as the auth source of truth

Rather than building a custom auth system, Firebase handles all identity operations in the browser — email and password auth, email verification, password reset, and anonymous access. The API only verifies Firebase ID tokens and syncs the Firebase UID into a local Postgres user record. This was the right call for moving fast and avoiding auth security pitfalls. The cost is a hard dependency on Firebase — swapping to a different auth provider later would require touching every route that checks for a verified user.

### Dual deployment mode supporting both Lambda and long-lived servers

Supporting two deployment modes adds complexity: two Dockerfiles, environment variables that change runtime behavior, and a Celery app that must stay in sync with the async inline path. The benefit is flexibility for different hosting cost models — Lambda for low-traffic and pay-per-invocation environments, a long-lived container for high-throughput use cases with background workers. In practice this means keeping synthesis chunked and bounded so it fits within Lambda's timeout constraints.

### Multiple Groq API keys for rate limit management

Groq's free tier has aggressive rate limits. Rather than a queue or retry backoff, the service rotates through up to five API keys on failures. This is practical for a demo but is not the right solution in production. A proper paid tier, rate-limit-aware queue, or circuit breaker pattern would be cleaner and more reliable.

### Prisma over SQLAlchemy

Prisma Client Python generates a strongly-typed client from the schema, which reduces mis-typed column names and makes schema changes visible in code immediately after running `prisma generate`. The tradeoff is that the Prisma Python client is newer and has less community tooling than SQLAlchemy, and some edge cases involving complex transactions or raw SQL require workarounds.

---

## What I'd Do Differently

Removing the dual deployment mode complexity is the first thing I would do. Maintaining two Dockerfiles and two runtime execution paths adds ongoing maintenance overhead. Picking one target infrastructure — containerized long-lived service with Celery — and optimizing for it would be cleaner than trying to be Lambda-compatible at the same time.

Replacing the Groq key rotation approach with proper rate limiting is the next priority. Rotating between API keys to avoid rate limits is fragile and hard to reason about. Production needs either a Groq paid tier with proper limits, a request queue that smooths out burst traffic, or a circuit breaker that gracefully degrades synthesis quality under load.

Adding a proper async job status and polling model for research runs would decouple job execution from the HTTP request lifecycle. Currently the client triggers research and waits on the same connection. A start-job / poll-status / fetch-result pattern would handle browser disconnects gracefully and scale better.

Tightening CORS for production deployments is a must. The current configuration allows wildcard origins in some paths for evaluator convenience, which cannot ship to real users.

Adding end-to-end tests for the research pipeline would catch wiring issues that unit tests miss. The current test surface is mostly at the service level with mocked external calls.

Real observability is missing. Structured logs exist but there is no telemetry pipeline. OpenTelemetry tracing through the LangGraph nodes, SerpAPI calls, and synthesis steps would make it possible to identify where slow requests are actually spending time.

---

## Notes for Frontend Integration

Development CORS allows `http://localhost:5173`, which is the default Vite dev server port used by Advista_client. Production CORS allows `https://advista.ayushjrathod.live` and Vercel preview deployments. The client must send Firebase ID tokens as `Authorization: Bearer <token>`. Unauthenticated visitors using anonymous Firebase sign-in can try the product flow but cannot access saved history or owned reports. Lambda-wrapped responses have an extra envelope that the client unwraps before consuming the payload.

---

## Troubleshooting

A `401 Could not validate credentials` error usually means the Firebase bearer token is missing or has expired. A `403 Please verify your email` error means the route requires a verified Firebase account. Empty research results typically point to a missing `SERPAPI_API_KEY` or malformed brief data. Groq synthesis failures usually mean the configured `GROQ_API_KEY*` values are missing or all rate-limited simultaneously. If Prisma fails on startup, run `uv run prisma generate` and verify that `DATABASE_URL` points to a reachable database. If the container fails to start on Cloud Run, check the `/health` response — the app starts even when the database is temporarily unavailable and reports DB connectivity state there.
