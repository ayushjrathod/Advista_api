# Advista API

FastAPI backend for Advista, a competitive intelligence and ad research assistant. The API handles Firebase-authenticated users, chat-based research brief collection, multi-source research gathering, report synthesis, and optional Celery-backed background work.

## What this project is

`Advista_api` is the backend half of the Advista product.

Its job is to:

- accept authenticated and anonymous client requests
- manage chat threads and research sessions
- turn a conversational brief into search queries
- collect source material from external services
- synthesize a final competitive intelligence report
- persist users, sessions, results, and reports in Postgres

In short: the client collects the user's input and renders the experience, while this API does the orchestration, data collection, storage, and report generation.

## What this service does

- Serves the main FastAPI app from `main.py`
- Syncs Firebase identities into the local Postgres user table
- Creates chat threads and incrementally builds a research brief
- Runs SerpAPI + YouTube research and synthesizes a report
- Stores chat sessions and research sessions through Prisma Client Python
- Supports both long-lived server mode and AWS Lambda container deployment

## Stack

- Python 3.13+
- FastAPI + Uvicorn
- Prisma Client Python + PostgreSQL
- Firebase Admin SDK
- LangChain / LangGraph + Groq
- SerpAPI + YouTube transcript extraction
- Optional Redis + Celery for background jobs
- Mangum for AWS Lambda

## Project layout

```text
.
├── main.py                  # FastAPI entrypoint
├── lambda_handler.py        # AWS Lambda handler via Mangum
├── prisma/schema.prisma     # DB schema and Prisma client config
├── src/controllers/         # Auth, chat, research routes
├── src/services/            # Auth, research, synthesis, integrations
├── src/repositories/        # Persistence helpers
├── worker/                  # Celery app + tasks
└── scripts/build-and-push-lambda.sh
```

## Where things are

If you are new to the backend, these are the folders and files you will touch most often:

- `main.py` — application bootstrap, CORS setup, route registration, health endpoints
- `lambda_handler.py` — Lambda entrypoint used when the API runs as a containerized AWS Lambda
- `prisma/schema.prisma` — database schema for users, chat sessions, and research sessions
- `src/controllers/` — HTTP route layer
- `src/models/` — Pydantic request/response models and research data structures
- `src/repositories/` — database access helpers and persistence logic
- `src/services/` — business logic and external integrations
- `src/services/serpapi_clients/` — smaller focused clients for specific SerpAPI engines
- `src/utils/config.py` — environment variable loading and settings
- `worker/` — Celery app and background task wiring
- `scripts/` — deployment and operational scripts

### Backend flow by area

- **Authentication** lives in `src/controllers/auth_controller.py`, `src/services/auth_service.py`, and `src/services/firebase_service.py`
- **Chat + research brief generation** lives in `src/controllers/chat_controller.py` and `src/services/chatbot_service.py`
- **Research query generation** lives in `src/services/research_service.py`
- **Search collection and source ingestion** lives in `src/services/serpapi_service.py`, `src/services/serpapi_clients/`, and `src/services/youtube_service.py`
- **Result processing** lives in `src/services/analysis_service.py`
- **Report synthesis** lives in `src/services/synthesis_service.py`
- **Research session persistence** lives in `src/services/research_session_service.py` and `src/repositories/research_session_repository.py`

### Data you may notice in the repo root

These files are mostly local debug artifacts produced during research runs:

- `search_params.json`
- `search_results.json`
- `processed_results.json`
- `research_context.txt`
- `research_report.json`

They are useful for inspecting pipeline output locally, but the primary source of truth in normal app usage is the database.

## Prerequisites

- Python 3.13 or newer
- `uv` installed for dependency management
- PostgreSQL database
- Prisma CLI available through the Python package setup
- Firebase project for auth
- SerpAPI key
- At least one Groq API key
- Redis only if you want Celery-enabled async workers locally

## Environment variables

Create `.env` in `Advista_api/`.

### Required for local development

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

### Optional mail settings

```env
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_FROM=
MAIL_PORT=587
MAIL_SERVER=smtp.gmail.com
MAIL_STARTTLS=true
MAIL_SSL_TLS=false
```

### Optional local debug output

```env
ENABLE_DEBUG_FILES=true
```

When enabled, research intermediates are written to `search_results.json`, `processed_results.json`, `research_context.txt`, and `research_report.json`.

## Local setup

### 1. Install dependencies

```bash
uv sync
```

### 2. Generate the Prisma client

```bash
uv run prisma generate
```

### 3. Apply schema changes

Use whichever workflow matches your database process:

```bash
uv run prisma migrate deploy
```

or during local schema iteration:

```bash
uv run prisma db push
```

### 4. Start the API

```bash
uv run uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The app is available at:

- `http://localhost:8000/`
- `http://localhost:8000/health`

## Running with Redis + Celery

If you want worker-backed research execution instead of the Lambda-friendly in-process async path:

1. Set `ENABLE_CELERY=true` and `ENABLE_REDIS=true`
2. Start the stack:

```bash
docker compose up --build
```

This starts:

- `advista_api` on port `8000`
- `redis` on port `6379`
- `celery_worker`

## API overview

Base prefixes:

- `/api/v1/auth`
- `/api/v1/chat`
- `/api/v1/research`

### Key routes

#### Auth

- `GET /api/v1/auth/me` — returns current auth state if a Firebase bearer token is present
- `GET /api/v1/auth/check-email-unique?email=...` — checks whether an email is already claimed
- `POST /api/v1/auth/logout` — no-op success response for client-side Firebase logout

Note: legacy email/password signup and reset endpoints still exist but intentionally return `410 Gone` because Firebase client auth is the source of truth now.

#### Chat

- `GET|POST /api/v1/chat/initialize-thread` — creates a chat thread
- `POST /api/v1/chat/stream` — streams the chatbot response as Server-Sent Events
- `GET /api/v1/chat/research-brief/{thread_id}` — returns the current brief, completion %, and missing fields

#### Research

- `POST /api/v1/research/start-research` — runs the full research pipeline
- `GET /api/v1/research/sessions` — returns saved research history for the current user
- `GET /api/v1/research/report?session_id=...` — fetches a completed report
- `GET /api/v1/research/processed-results` — local debug endpoint backed by `processed_results.json`

## Deployment

### AWS Lambda container

The Lambda handler is `lambda_handler.handler`.

To build and push the Lambda image to ECR:

```bash
./scripts/build-and-push-lambda.sh
```

Examples:

```bash
./scripts/build-and-push-lambda.sh personal
./scripts/build-and-push-lambda.sh --no-cache
./scripts/build-and-push-lambda.sh personal --no-cache
```

The script:

- builds `Dockerfile.lambda`
- targets `linux/amd64` for Lambda compatibility
- tags and pushes `590184115599.dkr.ecr.ap-south-1.amazonaws.com/advista/advista_api:latest`

### Standard container runtime

For long-lived environments, `Dockerfile` + `docker-compose.yml` run the API with optional Redis and Celery.

## Notes for frontend integration

- Local client origin `http://localhost:5173` is allowed in development
- Production CORS allows `https://advista.ayushjrathod.live` and Vercel deployments
- The client should send Firebase bearer tokens in the `Authorization` header
- Unauthenticated visitors can still explore parts of the product, but saved history/report ownership depends on a synced Firebase user

## Troubleshooting

- `401 Could not validate credentials` usually means the Firebase bearer token is missing or invalid
- `403 Please verify your email...` means the route requires a verified Firebase user
- Empty research results usually point to missing `SERPAPI_API_KEY` or malformed research brief data
- Groq synthesis failures usually mean the configured `GROQ_API_KEY*` values are missing or rate-limited
- If Prisma fails on startup, regenerate the client and verify `DATABASE_URL`
