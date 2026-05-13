import time
import uuid

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth.router import router as auth_router
from app.auth.security import decode_token, get_current_user
from app.core.logging import configure_logging, get_logger
from app.core.metrics import build_metrics_response, observe_http_request
from app.core.rate_limit import RateLimitMiddleware
from app.core.request_context import (
    clear_request_context,
    set_request_id,
    set_user_id,
)
from app.documents.embedding_router import router as document_embeddings_router
from app.documents.router import router as documents_router
from app.query.router import router as query_router

# Configuramos el logging antes de crear la app,
# para que cualquier log ya salga en JSON desde el principio.
configure_logging()
logger = get_logger(__name__)

app = FastAPI(title="Archivum API")

"""
Configuración CORS para permitir peticiones desde el frontend React.

En desarrollo, Vite levanta el frontend normalmente en http://localhost:5173.
Sin esta configuración, el navegador bloquearía las llamadas al backend
por venir desde otro origen distinto.
"""
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware transversal ya existente para rate limiting.
app.add_middleware(RateLimitMiddleware)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """
    Middleware transversal de observabilidad.

    Su trabajo es:
    - generar un request_id único
    - intentar identificar al usuario autenticado
    - medir la latencia de la petición
    - registrar un log estructurado en JSON
    - publicar métricas HTTP para Prometheus
    """
    request_id = str(uuid.uuid4())
    set_request_id(request_id)

    # Guardamos el request_id también en request.state por si
    # algún endpoint quiere reutilizarlo más adelante.
    request.state.request_id = request_id

    # Valor por defecto cuando no hay usuario autenticado.
    set_user_id("-")

    start_time = time.perf_counter()
    response = None
    status_code = 500

    try:
        # Intentamos extraer el user_id desde el token Bearer
        # sin romper la petición si el token no existe o es inválido.
        authorization = request.headers.get("Authorization")

        if authorization and authorization.startswith("Bearer "):
            token = authorization.removeprefix("Bearer ").strip()

            if token:
                try:
                    payload = decode_token(token)
                    token_type = payload.get("type")
                    token_user_id = payload.get("sub")

                    if token_type == "access" and token_user_id:
                        set_user_id(str(token_user_id))
                except ValueError:
                    # Si el token no es válido, no rompemos el flujo aquí.
                    # Ya se encargará luego la seguridad del endpoint.
                    pass

        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception:
        # Si algo explota antes de construir respuesta,
        # dejamos constancia en el log.
        logger.exception(
            "Error no controlado durante la petición",
            extra={
                "event_data": {
                    "event": "request_error",
                    "path": request.url.path,
                    "method": request.method,
                }
            },
        )
        raise
    finally:
        duration_seconds = time.perf_counter() - start_time
        duration_ms = round(duration_seconds * 1000, 2)

        observe_http_request(
            method=request.method,
            path=request.url.path,
            status_code=status_code,
            duration_seconds=duration_seconds,
        )

        logger.info(
            "Petición procesada",
            extra={
                "event_data": {
                    "event": "http_request",
                    "path": request.url.path,
                    "method": request.method,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            },
        )

        # Añadimos request_id a la respuesta para poder
        # cruzar cliente, logs y métricas con más facilidad.
        if response is not None:
            response.headers["X-Request-ID"] = request_id

        clear_request_context()


# Router de autenticación.
app.include_router(auth_router)

# Router principal de documentos.
app.include_router(documents_router)

# Router de embeddings de R40.
app.include_router(document_embeddings_router)

# Router de consultas usado por R50-R56.
app.include_router(query_router)


@app.get("/metrics", tags=["observability"])
async def metrics():
    """
    Endpoint de métricas compatible con Prometheus.
    """
    return build_metrics_response()


@app.get("/protected")
async def protected(user=Depends(get_current_user)):
    """
    Endpoint mínimo para comprobar que el access token funciona.
    """
    return {
        "ok": True,
        "user_id": str(user.id),
        "email": user.email,
        "roles": [role.name for role in user.roles],
    }