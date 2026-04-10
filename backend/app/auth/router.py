import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.auth.repository import RefreshTokenRepository
from app.auth.schemas import (
    AssignRoleRequest,
    CurrentUserResponse,
    RefreshRequest,
    TokenPair,
)
from app.auth.security import (
    get_current_active_user,
    require_roles,
)
from app.auth.service import AuthService
from app.core.db import get_session
from app.users.repository import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


def get_auth_service(session: Session = Depends(get_session)) -> AuthService:
    """
    Construye el servicio de autenticación con sus repositorios.
    """
    user_repo = UserRepository(session)
    refresh_repo = RefreshTokenRepository(session)
    return AuthService(user_repo=user_repo, refresh_repo=refresh_repo)


def build_current_user_response(user) -> CurrentUserResponse:
    """
    Convierte un usuario ORM en una respuesta simple y clara.
    """
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_active=user.is_active,
        roles=[role.name for role in user.roles],
    )


@router.post("/login", response_model=TokenPair)
async def login(
    form: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service),
):
    """
    Login usando el formulario estándar OAuth2.
    """
    try:
        access_token, refresh_token = service.login(
            email=form.username,
            password=form.password,
        )
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
):
    """
    Renueva la sesión a partir de un refresh token válido.
    """
    try:
        access_token, refresh_token = service.refresh(body.refresh_token)
        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
        ) from exc


@router.get("/me", response_model=CurrentUserResponse)
async def get_me(
    user=Depends(get_current_active_user),
):
    """
    Devuelve la información del usuario autenticado junto a sus roles.
    """
    return build_current_user_response(user)


@router.get("/users", response_model=list[CurrentUserResponse])
async def list_users(
    session: Session = Depends(get_session),
    admin_user=Depends(require_roles("admin")),
):
    """
    Devuelve todos los usuarios.
    Solo el rol admin puede usar este endpoint.
    """
    user_repo = UserRepository(session)
    users = user_repo.list_all()
    return [build_current_user_response(user) for user in users]


@router.post("/users/{user_id}/roles", response_model=CurrentUserResponse)
async def assign_role_to_user(
    user_id: uuid.UUID,
    body: AssignRoleRequest,
    session: Session = Depends(get_session),
    admin_user=Depends(require_roles("admin")),
):
    """
    Asigna un rol a un usuario.
    Solo admin puede hacerlo.
    """
    user_repo = UserRepository(session)

    target_user = user_repo.find_by_id(user_id)
    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario objetivo no encontrado",
        )

    role = user_repo.get_role_by_name(body.role_name)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Rol no encontrado",
        )

    updated_user = user_repo.assign_role(target_user, role)
    return build_current_user_response(updated_user)