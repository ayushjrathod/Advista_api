import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.utils.config import settings
from src.controllers.auth_controller import auth_router
from src.controllers.chat_controller import chat_router
from src.controllers.research_controller import research_router
from src.services.database_service import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _is_lambda() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))


async def lifespan(app: FastAPI):
    await db.connect()
    yield
    # In Lambda, reuse connection across warm invocations; don't disconnect
    if not _is_lambda():
        await db.disconnect()

app = FastAPI(
    title = "Advista",
    description = "Advertisement Research Engine",
    lifespan=lifespan,
    version = "2.0.0"
)

# CORS configuration
allowed_origins = []

# Add development origins
if settings.ENVIRONMENT == "development":
    allowed_origins.extend([
        "http://localhost:3000",
        "http://localhost:5173",  # Vite default port
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ])

if settings.ENVIRONMENT == "production":
    allowed_origins.extend([
        "https://advista.ayushjrathod.live",
        "https://advista-prod.vercel.app",
    ])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"^https://(.*\.vercel\.app|advista\.ayushjrathod\.live)$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=[
        "Accept",
        "Accept-Language",
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Origin",
        "Access-Control-Request-Method",
        "Access-Control-Request-Headers",
    ],
    expose_headers=["*"],
)



# Include authentication routes
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(chat_router, prefix="/api/v1/chat")
app.include_router(research_router, prefix="/api/v1/research")

@app.get("/")
async def root():
    return JSONResponse(content={"status": "ok", "message": "Advista API is running"}, status_code=200)

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "ok", "message": "Advista API is healthy"}, status_code=200)


@app.get("/api/v1/keep-alive")
async def keep_alive():
    """
    Ping endpoint to prevent Supabase DB from sleeping (free tier).
    Called by GitHub Actions every 6 days.
    """
    try:
        # Run a lightweight query to wake up the DB connection
        await db.connect()
        await db.prisma.user.find_first()
        return JSONResponse(
            content={"status": "ok", "message": "Database keep-alive successful"},
            status_code=200,
        )
    except Exception as e:
        logger.error(f"Keep-alive failed: {e}")
        return JSONResponse(
            content={"status": "error", "message": str(e)},
            status_code=500,
        )

# Celery task endpoints (only enabled if ENABLE_CELERY is True)
if settings.ENABLE_CELERY:
    @app.post('/tasks/append-task')
    async def append_task(data: dict):
        from worker.celery_app import celery_app
        result = celery_app.send_task('process_data', args=[data])
        return JSONResponse(content={
            "task_id": result.id,
            "status": "task submitted"
        })

    @app.get("/tasks/task-status/{task_id}")
    async def get_task_status(task_id: str):
        from worker.celery_app import celery_app
        import json

        result = celery_app.AsyncResult(task_id)

        if result.ready():
            # Ensure the task status and result are JSON-serializable
            status = str(result.status)
            raw_result = result.result
            try:
                json.dumps(raw_result)
                safe_result = raw_result
            except (TypeError, ValueError):
                safe_result = str(raw_result)

            return JSONResponse(content={
                "task_id": task_id,
                "status": status,
                "result": safe_result
            })
        else:
            return JSONResponse(content={
                "task_id": task_id,
                "status": "pending"
            })

if __name__ == "__main__":
    import uvicorn 
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)

