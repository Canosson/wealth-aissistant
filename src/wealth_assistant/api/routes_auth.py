"""Auth routes: POST /auth/register and POST /auth/login (T019)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from wealth_assistant.api.deps import SessionDep
from wealth_assistant.api.limiter import limiter
from wealth_assistant.api.schemas import AuthResponse, LoginRequest, RegisterRequest
from wealth_assistant.domain.errors import ConflictError, ValidationError
from wealth_assistant.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, session: SessionDep) -> AuthResponse:
    try:
        investor, token = await AuthService(session).register(
            email=str(body.email),
            password=body.password,
            reporting_currency=body.reporting_currency,
        )
    except ConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "email_conflict", "message": exc.message},
        )
    return AuthResponse(token=token, investor_id=investor.id)


@router.post("/login", response_model=AuthResponse)
@limiter.limit("5/minute")
async def login(request: Request, body: LoginRequest, session: SessionDep) -> AuthResponse:
    try:
        investor, token = await AuthService(session).login(
            email=str(body.email),
            password=body.password,
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "invalid_credentials", "message": exc.message},
        )
    return AuthResponse(token=token, investor_id=investor.id)
