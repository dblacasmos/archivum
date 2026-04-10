from dataclasses import dataclass

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.auth.security import decode_token
from app.core.config import settings
from app.core.redis_client import redis_client


@dataclass(frozen=True)
class RateLimitRule:
    """
    Regla de limitación para un endpoint concreto.
    """

    max_requests: int
    window_seconds: int
    key_mode: str  # "ip" o "user_or_ip"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware transversal de rate limiting.

    Reglas aplicadas:
    - /auth/login -> por IP
    - /query -> por usuario autenticado y, si no hay token válido, fallback a IP
    - /documents/upload -> por usuario autenticado y, si no hay token válido, fallback a IP
    """

    def __init__(self, app):
        super().__init__(app)

        # Diccionario con las reglas por método + path.
        self.rules: dict[tuple[str, str], RateLimitRule] = {
            ("POST", "/auth/login"): RateLimitRule(
                max_requests=settings.rate_limit_login_max_requests,
                window_seconds=settings.rate_limit_login_window_seconds,
                key_mode="ip",
            ),
            ("POST", "/query"): RateLimitRule(
                max_requests=settings.rate_limit_query_max_requests,
                window_seconds=settings.rate_limit_query_window_seconds,
                key_mode="user_or_ip",
            ),
            ("POST", "/documents/upload"): RateLimitRule(
                max_requests=settings.rate_limit_upload_max_requests,
                window_seconds=settings.rate_limit_upload_window_seconds,
                key_mode="user_or_ip",
            ),
        }

    async def dispatch(self, request: Request, call_next):
        """
        Intercepta la petición antes de llegar al endpoint real.
        Si se supera el límite, devuelve 429.
        """
        # Si el sistema está desactivado, se deja pasar todo.
        if not settings.rate_limit_enabled:
            return await call_next(request)

        # Buscamos si la petición actual tiene una regla definida.
        rule = self.rules.get((request.method.upper(), request.url.path))

        # Si no hay regla, no tocamos nada y dejamos pasar.
        if rule is None:
            return await call_next(request)

        # Obtenemos la identidad con la que contaremos las peticiones.
        identifier = self._build_identifier(request=request, key_mode=rule.key_mode)

        # La clave final de Redis combina endpoint + identificador + ventana.
        redis_key = f"rate_limit:{request.method}:{request.url.path}:{identifier}"

        # Incrementamos el contador.
        current_requests = redis_client.incr(redis_key)

        # Solo la primera petición crea la caducidad de la ventana.
        if current_requests == 1:
            redis_client.expire(redis_key, rule.window_seconds)

        # Consultamos cuánto tiempo queda para reiniciar el contador.
        ttl_seconds = redis_client.ttl(redis_key)
        if ttl_seconds is None or ttl_seconds < 0:
            ttl_seconds = rule.window_seconds

        # Si supera el límite, devolvemos 429 sin entrar al endpoint.
        if current_requests > rule.max_requests:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Has superado el límite de peticiones permitido. Inténtalo de nuevo en unos segundos."
                },
                headers={
                    "Retry-After": str(ttl_seconds),
                    "X-RateLimit-Limit": str(rule.max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(ttl_seconds),
                },
            )

        # Si todavía está dentro del límite, continuamos normalmente.
        response = await call_next(request)

        # Añadimos cabeceras informativas útiles para depuración.
        remaining = max(rule.max_requests - current_requests, 0)
        response.headers["X-RateLimit-Limit"] = str(rule.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(ttl_seconds)

        return response

    def _build_identifier(self, request: Request, key_mode: str) -> str:
        """
        Construye el identificador que se usará en Redis.

        - Para login usamos la IP
        - Para query/upload usamos user_id si hay token Bearer válido
        - Si no existe token válido, hacemos fallback a IP
        """
        client_ip = self._get_client_ip(request)

        if key_mode == "ip":
            return f"ip:{client_ip}"

        user_id = self._get_user_id_from_bearer_token(request)
        if user_id is not None:
            return f"user:{user_id}"

        return f"ip:{client_ip}"

    def _get_client_ip(self, request: Request) -> str:
        """
        Obtiene la IP del cliente.

        Si existe X-Forwarded-For, usa la primera IP.
        Si no, usa request.client.host.
        """
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()

        if request.client and request.client.host:
            return request.client.host

        return "unknown"

    def _get_user_id_from_bearer_token(self, request: Request) -> str | None:
        """
        Intenta extraer el user_id desde el JWT Bearer.
        Si el token no existe o es inválido, devuelve None.
        """
        authorization = request.headers.get("Authorization")
        if not authorization:
            return None

        prefix = "Bearer "
        if not authorization.startswith(prefix):
            return None

        token = authorization[len(prefix):].strip()
        if not token:
            return None

        try:
            payload = decode_token(token)
        except ValueError:
            return None

        if payload.get("type") != "access":
            return None

        user_id = payload.get("sub")
        if not user_id:
            return None

        return str(user_id)