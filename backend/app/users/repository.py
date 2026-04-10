from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models.role import Role
from app.users.models import User


class UserRepository:
    """Encargado de guardar y buscar usuarios en la base de datos."""

    def __init__(self, db: Session):
        # Recibe una sesión activa de base de datos
        self.db = db

    def create(self, user: User) -> User:
        # Añade el usuario a la sesión
        self.db.add(user)

        # Guarda los cambios en la base de datos
        self.db.commit()

        # Recarga el objeto desde la base de datos
        self.db.refresh(user)

        # Devuelve el usuario persistido
        return user

    def find_by_id(self, user_id) -> User | None:
        # Busca un usuario por su clave primaria
        return self.db.get(User, user_id)

    def find_by_email(self, email) -> User | None:
        # Busca un usuario por email
        stmt = select(User).where(User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def list_all(self) -> list[User]:
        # Devuelve todos los usuarios del sistema
        stmt = select(User).order_by(User.created_at.asc())
        return list(self.db.execute(stmt).scalars().all())

    def get_role_by_name(self, role_name: str) -> Role | None:
        # Busca un rol por nombre
        stmt = select(Role).where(Role.name == role_name)
        return self.db.execute(stmt).scalar_one_or_none()

    def assign_role(self, user: User, role: Role) -> User:
        """
        Asigna un rol al usuario si todavía no lo tiene.
        """
        current_role_names = {item.name for item in user.roles}

        if role.name not in current_role_names:
            user.roles.append(role)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

        return user