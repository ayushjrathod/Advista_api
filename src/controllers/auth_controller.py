from fastapi import APIRouter, HTTPException, Depends, status, Request, Response
from src.models.user import (
    UserCreate, UserResponse, UserSignIn, 
    VerifyCodeRequest, ForgotPasswordRequest, 
    ResetPasswordRequest, MessageResponse
)
from src.services.auth_service import auth_service
from src.utils.config import settings
import logging

logger = logging.getLogger(__name__)

auth_router = APIRouter()

async def get_current_user(request: Request):
    """Get current authenticated user from HttpOnly cookie"""
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    email = auth_service.verify_token(token)
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return email

@auth_router.get("/check-email-unique", response_model=MessageResponse)
async def check_email_unique(email: str):
    """Check if email is unique"""
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    try:
        user = await auth_service.prisma.user.find_unique(where={"email": email})
        if user:
            return MessageResponse(message="Email is already taken", success=True)
        else:
            return MessageResponse(message="Email is available", success=True)
    except Exception as e:
        logger.error(f"Check email unique error: {str(e)}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

@auth_router.post("/signup", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate):
    """Register a new user"""
    try:
        # Validate password confirmation
        if user_data.password != user_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match"
            )
        
        result = await auth_service.create_user(user_data.email, user_data.password)
        
        return MessageResponse(
            message=result["message"],
            success=True
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@auth_router.post("/signin", response_model=MessageResponse)
async def signin(user_credentials: UserSignIn, response: Response):
    """Authenticate user and set HttpOnly cookie"""
    try:
        result = await auth_service.authenticate_user(
            user_credentials.email, 
            user_credentials.password
        )
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Set HttpOnly cookie
        response.set_cookie(
            key="access_token",
            value=result["access_token"],
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            max_age=settings.COOKIE_MAX_AGE
        )
        
        return MessageResponse(
            message="Sign in successful",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signin error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@auth_router.post("/logout", response_model=MessageResponse)
async def logout(response: Response):
    """Logout user by clearing HttpOnly cookie"""
    response.delete_cookie(
        key="access_token",
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )
    
    return MessageResponse(
        message="Logged out successfully",
        success=True
    )

@auth_router.post("/verify-email", response_model=MessageResponse)
async def verify_email(verify_data: VerifyCodeRequest):
    """Verify user email with verification code"""
    try:
        success = await auth_service.verify_email(
            verify_data.email, 
            verify_data.verify_code
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code"
            )
        
        return MessageResponse(
            message="Email verified successfully",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@auth_router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(forgot_data: ForgotPasswordRequest):
    """Send password reset code to user email"""
    try:
        success = await auth_service.forgot_password(forgot_data.email)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return MessageResponse(
            message="Password reset code sent to your email",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Forgot password error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@auth_router.post("/reset-password", response_model=MessageResponse)
async def reset_password(reset_data: ResetPasswordRequest):
    """Reset user password with reset code"""
    try:
        # Validate password confirmation
        if reset_data.new_password != reset_data.confirm_password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passwords do not match"
            )
        
        success = await auth_service.reset_password(
            reset_data.email,
            reset_data.reset_code,
            reset_data.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset code"
            )
        
        return MessageResponse(
            message="Password reset successfully",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Reset password error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@auth_router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification_code(request_data: ForgotPasswordRequest):
    """Resend verification code to user email"""
    try:
        success = await auth_service.resend_verification_code(request_data.email)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found or already verified"
            )
        
        return MessageResponse(
            message="Verification code sent successfully",
            success=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resend verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@auth_router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: str = Depends(get_current_user)):
    """Get current user information"""
    try:
        user = await auth_service.prisma.user.find_unique(where={"email": current_user})
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserResponse(
            id=user.id,
            email=user.email,
            is_verified=user.isVerified,
            created_at=user.createdAt,
            updated_at=user.updatedAt
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get user info error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
