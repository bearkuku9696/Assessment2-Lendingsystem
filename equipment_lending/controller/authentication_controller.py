from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from equipment_lending.database import DatabaseSession
from equipment_lending.model.user import User
from equipment_lending.schema.authentication import LoginRequest, LoginResponse, RegisterRequest, UserResponse
from equipment_lending.service.authentication_service import (
    AuthenticationService, EmailAlreadyRegistered, InvalidCredentials, InvalidToken,
    TOKEN_LIFETIME_SECONDS,
)


router = APIRouter(prefix="/auth", tags=["Authentication"])
bearer = HTTPBearer()


def get_authentication_service(session: DatabaseSession) -> AuthenticationService:
    return AuthenticationService(session)


AuthService = Annotated[AuthenticationService, Depends(get_authentication_service)]


@router.post("/register", response_model=UserResponse, status_code=201)
def register(data: RegisterRequest, service: AuthService):
    try:
        return service.register(data.name, str(data.email), data.password)
    except EmailAlreadyRegistered:
        raise HTTPException(409, "An account already exists for this email address.") from None


@router.post("/login", response_model=LoginResponse)
def login(data: LoginRequest, service: AuthService, response: Response):
    try:
        token, user = service.login(str(data.email), data.password)
    except InvalidCredentials:
        raise HTTPException(401, "Invalid email address or password.", headers={"WWW-Authenticate": "Bearer"}) from None
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(access_token=token, expires_in=TOKEN_LIFETIME_SECONDS, user=UserResponse.model_validate(user))


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)], service: AuthService
) -> User:
    try:
        return service.current_user(credentials.credentials)
    except InvalidToken:
        raise HTTPException(401, "Invalid or expired access token.", headers={"WWW-Authenticate": "Bearer"}) from None


@router.get("/me", response_model=UserResponse)
def me(user: Annotated[User, Depends(get_current_user)]):
    return user
