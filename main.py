import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from src.utils.config import settings
from src.controllers.auth_controller import router as auth_router
from src.controllers.chat_controller import router as chat_router
from src.controllers.research_controller import router as research_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title = "Advista",
    description = "Advertisement Research Engine",
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

if __name__ == "__main__":
    import uvicorn 
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT)

