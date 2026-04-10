import uuid

from pydantic import BaseModel, ConfigDict


class TokenPair(BaseModel):
    """
    Respuesta estándar que devuelve la API tras login o refresh.
    """

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    """
    Cuerpo que envía el cliente para renovar la sesión.
    """

    refresh_token: str


class AssignRoleRequest(BaseModel):
    """
    Cuerpo para asignar un rol a un usuario.
    """

    role_name: str


class CurrentUserResponse(BaseModel):
    """
    Respuesta con la información del usuario autenticado.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str | None
    is_active: bool
    roles: list[str]