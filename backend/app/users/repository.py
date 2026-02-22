from sqlalchemy import select
from sqlalchemy.orm import Session

from app.users.models import User

class UserRepository:
    '''Encargada de guardar y buscar usuarios en la base de datos'''

    def __init__(self, db: Session):
        # Recibe una sesión (conexión activa con la DB)
        self.db = db
    
    def create (self, user: User) -> User:
        # Añade al usuario a la sesión (aún no lo guarda)
        self.db.add(user)

        # Guarda los cambios en PostgreSQL
        self.db.commit()

        # Recarga el objeto desde la base de datos (para obtener id, timestamps, etc)
        self.db.refresh(user)

        # Devuelve el usuario ya persistido
        return user
    
    def find_by_id(self, user_id) -> User | None:
        # Busca por clave primaria (id)
        return self.db.get(User, user_id)
    
    def find_by_email(self, email) -> User | None:
        # Construye la consulta: SELECT * FROM users WHERE email = ...
        stmt = select(User).where (User.email == email)

        # Ejecuta la consulta y devuelve uno o ninguno
        return self.db.execute(stmt).scalar_one_or_none()