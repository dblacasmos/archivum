from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.models.refresh_token import RefreshToken


class RefreshTokenRepository:
    """
    Repositorio encargado de guardar, buscar y revocar refresh tokens.
    """

    def __init__(self, session: Session):
        self.session = session

    def create(self, token: RefreshToken) -> RefreshToken:
        """
        Guarda un refresh token nuevo en base de datos.
        """
        self.session.add(token)
        self.session.commit()
        self.session.refresh(token)
        return token

    def get_by_jti(self, jti: str) -> RefreshToken | None:
        """
        Busca un refresh token por su identificador único JWT ID (jti).
        """
        result = self.session.execute(
            select(RefreshToken).where(RefreshToken.jti == jti)
        )
        return result.scalar_one_or_none()

    def revoke(self, jti: str) -> None:
        """
        Marca un refresh token como revocado para que no pueda reutilizarse.
        """
        self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.jti == jti)
            .values(revoked=True)
        )
        self.session.commit()