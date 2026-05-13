import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.tracking.models import TrackingEvent


class TrackingEventRepository:
    """
    Repositorio encargado de guardar y consultar eventos.

    Esta clase separa el acceso a base de datos de la lógica de negocio.
    Así el servicio no necesita saber cómo se construyen las consultas SQL.
    """

    def __init__(self, db: Session):
        # Guarda la sesión activa de base de datos.
        self.db = db

    def create(self, event: TrackingEvent) -> TrackingEvent:
        """
        Guarda un evento nuevo en base de datos.
        """
        # Añade el evento a la sesión actual.
        self.db.add(event)

        # Confirma los cambios en PostgreSQL.
        self.db.commit()

        # Recarga el evento para obtener datos generados por la BD.
        self.db.refresh(event)

        # Devuelve el evento ya persistido.
        return event

    def list_recent(
        self,
        limit: int = 50,
        user_id: uuid.UUID | None = None,
    ) -> list[TrackingEvent]:
        """
        Devuelve los eventos más recientes.

        Si se recibe user_id, filtra solo por eventos de ese usuario.
        """
        # Construye la consulta base ordenando de más nuevo a más antiguo.
        stmt = select(TrackingEvent).order_by(TrackingEvent.created_at.desc())

        # Si se indica usuario, limita los resultados a ese usuario.
        if user_id is not None:
            stmt = stmt.where(TrackingEvent.user_id == user_id)

        # Aplica límite para no devolver demasiados datos.
        stmt = stmt.limit(limit)

        # Ejecuta la consulta y devuelve una lista de eventos.
        return list(self.db.execute(stmt).scalars().all())