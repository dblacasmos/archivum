from datetime import datetime, timedelta, timezone

from passlib.context import CryptContext

from app.auth.models.refresh_token import RefreshToken
from app.auth.repository import RefreshTokenRepository
from app.auth.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_token,
    new_jti,
)
from app.core.config import settings
from app.users.repository import UserRepository

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthService:
    """
    Servicio que contiene la lógica real de autenticación.
    """

    def __init__(self, user_repo: UserRepository, refresh_repo: RefreshTokenRepository):
        self.user_repo = user_repo
        self.refresh_repo = refresh_repo

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Comprueba si la contraseña escrita por el usuario coincide con su hash.
        """
        return pwd_context.verify(plain_password, hashed_password)

    def login(self, email: str, password: str) -> tuple[str, str]:
        """
        Valida credenciales y devuelve access + refresh token.
        """
        user = self.user_repo.find_by_email(email)
        if user is None:
            raise ValueError("Credenciales inválidas")

        if not self.verify_password(password, user.password_hash):
            raise ValueError("Credenciales inválidas")

        access_token = create_access_token(subject=user.id)

        refresh_jti = new_jti()
        refresh_token = create_refresh_token(subject=user.id, jti=refresh_jti)

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expires_days
        )

        self.refresh_repo.create(
            RefreshToken(
                user_id=user.id,
                jti=refresh_jti,
                token_hash=hash_token(refresh_token),
                revoked=False,
                expires_at=expires_at,
            )
        )

        return access_token, refresh_token

    def refresh(self, refresh_token: str) -> tuple[str, str]:
        """
        Aplica rotación de refresh token.
        """
        payload = decode_token(refresh_token)

        if payload.get("type") != "refresh":
            raise ValueError("Not a refresh token")

        jti = payload.get("jti")
        subject = payload.get("sub")

        if not jti or not subject:
            raise ValueError("Invalid refresh token payload")

        db_token = self.refresh_repo.get_by_jti(jti)
        if db_token is None:
            raise ValueError("Refresh token unknown")

        if db_token.revoked:
            raise ValueError("Refresh token revoked")

        expires_at_db = db_token.expires_at
        if expires_at_db.tzinfo is None:
            expires_at_db = expires_at_db.replace(tzinfo=timezone.utc)

        if expires_at_db <= datetime.now(timezone.utc):
            raise ValueError("Refresh token expired")

        if db_token.token_hash != hash_token(refresh_token):
            raise ValueError("Refresh token mismatch")

        self.refresh_repo.revoke(jti)

        new_access_token = create_access_token(subject=subject)

        new_refresh_jti = new_jti()
        new_refresh_token = create_refresh_token(subject=subject, jti=new_refresh_jti)

        new_expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expires_days
        )

        self.refresh_repo.create(
            RefreshToken(
                user_id=db_token.user_id,
                jti=new_refresh_jti,
                token_hash=hash_token(new_refresh_token),
                revoked=False,
                expires_at=new_expires_at,
            )
        )

        return new_access_token, new_refresh_token