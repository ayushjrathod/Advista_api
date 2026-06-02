from fastapi import APIRouter, HTTPException, Depends, status, Request
from src.models.user import (
    AuthStateResponse, UserResponse, MessageResponse
)
from src.services.auth_service import auth_service
from src.services.firebase_service import firebase_service
import logging

logger = logging.getLogger(__name__)

auth_router = APIRouter()

UNAUTHENTICATED_MESSAGE = (
    "You are not authenticated right now, but you can still continue this trial."
)


def _build_auth_state(current_user=None, message: str | None = None):
    user_payload = None
    if current_user:
        user_payload = UserResponse(
            id=current_user.id,
            email=current_user.email,
            is_verified=current_user.isVerified,
            created_at=current_user.createdAt,
            updated_at=current_user.updatedAt,
        )

    return AuthStateResponse(
        authenticated=bool(current_user),
        message=message or (
            "Authenticated successfully." if current_user else UNAUTHENTICATED_MESSAGE
        ),
        user=user_payload,
    )


async def get_optional_user(request: Request):
    """Return the Firebase-authenticated user when present, otherwise None."""
    authorization = request.headers.get("Authorization", "")
    scheme, _, token = authorization.partition(" ")

    if scheme.lower() != "bearer" or not token:
        return None

    try:
        claims = firebase_service.verify_id_token(token)
        return await auth_service.sync_firebase_user(claims)
    except Exception as exc:
        logger.warning(f"Optional bearer token verification failed: {str(exc)}")
        return None

async def get_current_user(request: Request):
    """Get current authenticated user from Firebase bearer token."""
    current_user = await get_optional_user(request)
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def get_verified_user(current_user = Depends(get_current_user)):
    """Require a Firebase-authenticated and email-verified user."""
    if not current_user.isVerified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email before accessing this resource",
        )
    return current_user


async def get_active_user(current_user = Depends(get_current_user)):
    """Require only a valid Firebase identity, including anonymous users."""
    return current_user

@auth_router.get("/check-email-unique", response_model=MessageResponse)
async def check_email_unique(email: str):
    """Check if email is unique"""
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    try:
        if not auth_service.is_email_available(email):
            return MessageResponse(message="Email is already taken", success=True)
        else:
            return MessageResponse(message="Email is available", success=True)
    except Exception as e:
        logger.error(f"Check email unique error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@auth_router.post("/logout", response_model=MessageResponse)
async def logout():
    """No-op logout endpoint for Firebase client auth."""
    return MessageResponse(
        message="Logged out successfully",
        success=True
    )

@auth_router.get("/me", response_model=AuthStateResponse)
async def get_current_user_info(current_user = Depends(get_optional_user)):
    """Get current user information without blocking unauthenticated visitors."""
    try:
        return _build_auth_state(current_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user info error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
