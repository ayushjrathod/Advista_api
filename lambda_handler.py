"""
AWS Lambda entry point for FastAPI.
Set Lambda handler to: lambda_handler.handler
Use with Lambda Function URL or API Gateway HTTP API.
"""
import os
from mangum import Mangum
from main import app

# Single Mangum instance reused across warm invocations
handler = Mangum(
    app,
    lifespan="auto",  # Run FastAPI lifespan (db.connect) on first request
    api_gateway_base_path=os.environ.get("API_GATEWAY_BASE_PATH", ""),
)
