# Archivum

Archivum es una plataforma de gestión documental inteligente desarrollada como Proyecto de Fin de Ciclo DAM.

El sistema incorpora:

- Gestión documental
- Búsqueda semántica e híbrida
- Vectorización mediante embeddings
- Flujo RAG (Retrieval-Augmented Generation)
- Control de acceso y seguridad
- Tracking de eventos y analítica
- Despliegue mediante Docker Compose

## Stack tecnológico

- FastAPI
- PostgreSQL + pgvector
- Redis
- React + Vite
- OpenAI API
- Docker Compose
- Prometheus
- Power BI

## Puesta en marcha

### Levantar entorno

```bash
docker compose up --build
```
## Ejecutar migraciones

```bash
docker compose exec backend alembic upgrade head
```

## Configurar API Key

Editar .env.docker:
OPENAI_API_KEY=tu_api_key

## Proyecto académico
Proyecto desarrollado para el ciclo de Desarrollo de Aplicaciones Multiplataforma (DAM).

Curso académico: 2024–2026.
