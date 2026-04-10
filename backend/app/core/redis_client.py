from redis import Redis

from app.core.config import settings

# Cliente Redis único para toda la aplicación.
# decode_responses=True hace que Redis devuelva strings normales
# en vez de bytes, lo cual simplifica bastante el código.
redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)