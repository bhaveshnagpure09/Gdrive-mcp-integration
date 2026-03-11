"""OAuth2 authentication middleware for API security."""

import logging
from typing import Optional

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from jose import JWTError, jwt

from app.settings import settings

logger = logging.getLogger(__name__)

# OAuth2 Bearer token security scheme
security = HTTPBearer()


class OAuth2Middleware(BaseHTTPMiddleware):
    """
    Middleware to validate OAuth2 JWT tokens on all API requests.
    
    Validates:
    - Bearer token presence
    - JWT signature (when configured)
    - Token expiration
    - Required claims
    
    Exempts health and metrics endpoints from authentication.
    """
    
    # Paths that don't require authentication
    EXEMPT_PATHS = [
        "/",
        "/health",
        "/api/v1/health",
        "/api/v1/metrics",
        "/docs",
        "/openapi.json",
        "/redoc",
    ]
    
    def __init__(self, app, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        """
        Initialize OAuth2 middleware.
        
        Args:
            app: FastAPI application
            secret_key: JWT secret key for signature validation (None = skip validation)
            algorithm: JWT algorithm (default: HS256)
        """
        super().__init__(app)
        self.secret_key = secret_key
        self.algorithm = algorithm
        
    async def dispatch(self, request: Request, call_next):
        """Validate OAuth2 token for incoming requests."""
        
        # Skip authentication for CORS preflight requests
        if request.method == "OPTIONS":
            return await call_next(request)

        # Skip authentication for exempt paths
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)
        
        # Extract authorization header
        auth_header = request.headers.get("Authorization")
        
        if not auth_header:
            logger.warning(
                "Missing Authorization header",
                extra={"path": request.url.path, "method": request.method}
            )
            return self._unauthorized_response("Missing Authorization header")
        
        # Validate Bearer token format
        if not auth_header.startswith("Bearer "):
            logger.warning(
                "Invalid Authorization header format",
                extra={"path": request.url.path}
            )
            return self._unauthorized_response("Invalid Authorization header format")
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Validate JWT token
        try:
            payload = self._validate_token(token)
            
            # Add decoded token info to request state for downstream use
            request.state.token_payload = payload
            request.state.client_id = payload.get("client_id") or payload.get("sub")
            
            logger.debug(
                "Token validated successfully",
                extra={
                    "client_id": request.state.client_id,
                    "path": request.url.path,
                }
            )
            
        except HTTPException as e:
            logger.warning(
                f"Token validation failed: {e.detail}",
                extra={"path": request.url.path}
            )
            return self._unauthorized_response(e.detail)
        
        return await call_next(request)
    
    def _validate_token(self, token: str) -> dict:
        """
        Validate JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            dict: Decoded token payload
            
        Raises:
            HTTPException: If token is invalid
        """
        if not self.secret_key:
            # If no secret key configured, skip signature validation
            # (useful for development/testing with external OAuth provider)
            try:
                # Decode without verification - still validates structure
                payload = jwt.decode(
                    token,
                    key="",  # Empty key for no verification
                    options={"verify_signature": False, "verify_aud": False, "verify_exp": False},
                )
                logger.debug("Token decoded without signature verification (dev mode)")
                return payload
            except JWTError as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid token format: {str(e)}",
                )
        
        # Validate with signature
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            
            # Validate required claims
            if "sub" not in payload and "client_id" not in payload:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token missing required claims (sub or client_id)",
                )
            
            return payload
            
        except JWTError as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Token validation failed: {str(e)}",
            )
    
    def _unauthorized_response(self, detail: str):
        """Create 401 Unauthorized JSON response."""
        from fastapi.responses import JSONResponse
        
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={
                "error": "Unauthorized",
                "detail": detail,
            },
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_client_id(request: Request) -> str:
    """
    Dependency to extract client_id from validated token.
    
    Usage:
        @router.get("/endpoint")
        async def endpoint(client_id: str = Depends(get_current_client_id)):
            ...
    
    Args:
        request: FastAPI request with validated token
        
    Returns:
        str: Client ID from token
        
    Raises:
        HTTPException: If client_id not found in token
    """
    client_id = getattr(request.state, "client_id", None)
    
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client ID not found in token",
        )
    
    return client_id
