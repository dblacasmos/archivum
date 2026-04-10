import contextvars


# Este contextvar guarda el identificador único de la petición actual.
# Lo usamos para que cualquier log generado durante la request
# pueda incluir el mismo request_id sin tener que pasarlo a mano.
request_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id",
    default="-",
)

# Este contextvar guarda el user_id asociado a la petición actual.
# Si la petición es pública o el usuario no está autenticado,
# se mantendrá con el valor por defecto "-".
user_id_context: contextvars.ContextVar[str] = contextvars.ContextVar(
    "user_id",
    default="-",
)


def set_request_id(request_id: str) -> None:
    """
    Guarda el request_id de la petición actual en el contexto.
    """
    request_id_context.set(request_id)


def get_request_id() -> str:
    """
    Devuelve el request_id actual.
    Si no existe, devuelve "-".
    """
    return request_id_context.get()


def set_user_id(user_id: str) -> None:
    """
    Guarda el user_id de la petición actual en el contexto.
    """
    user_id_context.set(user_id)


def get_user_id() -> str:
    """
    Devuelve el user_id actual.
    Si no existe, devuelve "-".
    """
    return user_id_context.get()


def clear_request_context() -> None:
    """
    Limpia el contexto al terminar la petición.

    Esto evita que una request deje datos "pegados"
    y contamine los logs de la siguiente.
    """
    request_id_context.set("-")
    user_id_context.set("-")