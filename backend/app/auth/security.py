import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import get_session
from app.users.repository import UserRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_token(token: str) -> str:
    """
    Genera el hash SHA-256 de un refresh token.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(subject: str | uuid.UUID) -> str:
    """
    Crea un JWT de acceso de vida corta.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=settings.access_token_expires_minutes)

    payload = {
        "sub": str(subject),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def create_refresh_token(subject: str | uuid.UUID, jti: str) -> str:
    """
    Crea un JWT refresh de vida más larga.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=settings.refresh_token_expires_days)

    payload = {
        "sub": str(subject),
        "type": "refresh",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }

    return jwt.encode(
        payload,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """
    Decodifica y valida un JWT.
    """
    try:
        return jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except JWTError as exc:
        raise ValueError("Token inválido") from exc


def new_jti() -> str:
    """
    Genera un identificador único para refresh tokens.
    """
    return uuid.uuid4().hex


def get_uuid_id_from_payload(payload: dict) -> uuid.UUID:
    """
    Convierte el campo 'sub' del JWT a UUID.
    """
    user_id = payload.get("sub")
    if not user_id:
        raise ValueError("Payload del token inválido")
    return uuid.UUID(user_id)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
):
    """
    Obtiene el usuario autenticado a partir del access token.
    """
    try:
        payload = decode_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        ) from exc

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tipo de token no válido",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Payload del token inválido",
        )

    user_repo = UserRepository(session)
    user = user_repo.find_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        )

    return user


def get_current_active_user(
    user=Depends(get_current_user),
):
    """
    Comprueba que el usuario autenticado siga activo.
    """
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El usuario está desactivado",
        )
    return user


def get_role_names(user) -> set[str]:
    """
    Devuelve los nombres de rol del usuario en formato conjunto.
    """
    return {role.name for role in user.roles}


def require_roles(*allowed_roles: str):
    """
    Dependency reutilizable para proteger endpoints por rol.
    """

    def dependency(user=Depends(get_current_active_user)):
        user_roles = get_role_names(user)

        if not user_roles.intersection(set(allowed_roles)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos suficientes para acceder a este recurso",
            )

        return user

    return dependency