import json
import logging
from datetime import datetime, timezone

from app.core.request_context import get_request_id, get_user_id


class JsonFormatter(logging.Formatter):
    """
    Formateador de logs en JSON.

    Convierte cada evento de logging en un objeto JSON legible
    por herramientas de monitorización, por consola o por ficheros.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Construye el JSON final del log.
        """
        log_data: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
            "user_id": get_user_id(),
        }

        # Si el log trae datos extra en record.event_data,
        # los mezclamos dentro del JSON principal.
        event_data = getattr(record, "event_data", None)
        if isinstance(event_data, dict):
            log_data.update(event_data)

        # Si hubo una excepción, también la añadimos al JSON.
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def configure_logging() -> None:
    """
    Configura el logging global de la aplicación en formato JSON.
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Eliminamos handlers anteriores para evitar logs duplicados.
    root_logger.handlers.clear()

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(JsonFormatter())

    root_logger.addHandler(stream_handler)


def get_logger(name: str) -> logging.Logger:
    """
    Devuelve un logger listo para usar en un módulo concreto.
    """
    return logging.getLogger(name)