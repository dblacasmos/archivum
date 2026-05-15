# Manual de instalación de Archivum

Este documento describe el proceso de instalación y despliegue local de Archivum.

El objetivo del manual es permitir que el sistema pueda arrancarse de forma clara, ordenada y verificable usando Docker Compose y el script de despliegue incluido en el proyecto.

---

## 1. Requisitos previos

Antes de iniciar la instalación, el equipo debe tener instaladas las siguientes herramientas:

- Docker Desktop
- Docker Compose
- PowerShell
- Git

También es necesario disponer del código fuente completo del proyecto Archivum.

---

## 2. Servicios incluidos en el despliegue

El despliegue local de Archivum levanta los siguientes servicios:

- Backend FastAPI
- Frontend React servido mediante Nginx
- PostgreSQL con soporte pgvector
- Redis
- Prometheus

Estos servicios se definen en el archivo `docker-compose.yml`.

---

## 3. Puertos utilizados

Durante el despliegue local, los servicios quedan disponibles en los siguientes puertos:

- Backend: `http://localhost:8000`
- Swagger del backend: `http://localhost:8000/docs`
- Frontend: `http://localhost:8080`
- Prometheus: `http://localhost:9090`
- PostgreSQL: `localhost:5433`
- Redis: `localhost:6379`

---

## 4. Variables de entorno

El despliegue con Docker utiliza el archivo `.env.docker`.

Este archivo contiene la configuración necesaria para que los contenedores puedan comunicarse entre sí dentro de la red de Docker.

Ejemplo de configuración principal:

```env
# URL interna de PostgreSQL usada por el backend dentro de Docker.
DATABASE_URL=postgresql+psycopg://archivum:archivum@db:5432/archivum

# Clave usada para firmar los tokens JWT en entorno local.
JWT_SECRET_KEY=super_secret_123456789

# URL interna de Redis usada por el backend dentro de Docker.
REDIS_URL=redis://redis:6379/0

# Carpeta interna donde el backend guarda los documentos subidos.
UPLOAD_DIR=/app/storage/documents

# Modelo de embeddings configurado para el sistema.
OPENAI_EMBEDDINGS_MODEL=text-embedding-3-small
```

Si se desea utilizar generación real de embeddings o respuestas con servicios externos, será necesario configurar también la variable `OPENAI_API_KEY`.

---

## 5. Instalación mediante script de despliegue

La forma recomendada de instalar y arrancar Archivum en local es utilizar el script desarrollado en R91.

Desde la raíz del proyecto, ejecutar:

```powershell
# Ejecuta el script de despliegue local de Archivum.
.\scripts\deploy.ps1
```

El script realiza automáticamente las siguientes acciones:

1. Comprueba que Docker está disponible.
2. Comprueba que existen los archivos obligatorios.
3. Detiene contenedores anteriores si existen.
4. Reconstruye las imágenes del backend y del frontend.
5. Arranca todos los servicios en segundo plano.
6. Aplica las migraciones de base de datos con Alembic.
7. Muestra el estado de los contenedores.
8. Comprueba que los endpoints principales responden.

---

## 6. Instalación manual alternativa

Si se prefiere ejecutar el despliegue paso a paso, se pueden usar los siguientes comandos desde la raíz del proyecto.

```powershell
# Detiene y elimina contenedores anteriores del proyecto.
docker compose down

# Construye las imágenes y arranca todos los servicios definidos en docker-compose.yml.
docker compose up --build -d

# Aplica las migraciones de base de datos dentro del contenedor del backend.
docker compose exec -T backend alembic upgrade head

# Muestra el estado actual de los contenedores.
docker compose ps
```

Esta alternativa realiza el mismo proceso principal que el script, pero de forma manual.

---

## 7. Verificación de la instalación

Una vez finalizado el despliegue, se deben comprobar los servicios principales.

```powershell
# Comprueba que Swagger del backend está disponible.
Invoke-WebRequest -Uri http://localhost:8000/docs -UseBasicParsing

# Comprueba que el frontend responde correctamente.
Invoke-WebRequest -Uri http://localhost:8080 -UseBasicParsing

# Comprueba que Prometheus está disponible.
Invoke-WebRequest -Uri http://localhost:9090 -UseBasicParsing
```

La instalación se considera correcta si:

- El backend responde en `http://localhost:8000/docs`.
- El frontend responde en `http://localhost:8080`.
- Prometheus responde en `http://localhost:9090`.
- Los contenedores aparecen en estado activo al ejecutar `docker compose ps`.

---

## 8. Comprobación visual recomendada

Para dejar evidencia del requisito R92, se recomienda capturar:

1. La ejecución del script `.\scripts\deploy.ps1`.
2. El estado de los contenedores con `docker compose ps`.
3. Swagger abierto en `http://localhost:8000/docs`.
4. El frontend abierto en `http://localhost:8080`.
5. Prometheus abierto en `http://localhost:9090`.

Estas capturas permiten demostrar que el manual es coherente con el despliegue real del sistema.

---

## 9. Detención del entorno

Cuando se quiera apagar el entorno local, ejecutar:

```powershell
# Detiene los contenedores del proyecto sin borrar los volúmenes persistentes.
docker compose down
```

Los datos de PostgreSQL y los documentos subidos se conservan porque Docker Compose utiliza volúmenes persistentes.

---

## 10. Relación con otros requisitos

Este manual está relacionado directamente con:

- R90: Docker Compose
- R91: Script de despliegue
- R92: Manual de instalación

R90 define los servicios necesarios para ejecutar el sistema.

R91 automatiza el arranque del entorno mediante un script.

R92 documenta el procedimiento completo para que la instalación pueda repetirse y verificarse de forma sencilla.

---

## 11. Resultado esperado

Al finalizar la instalación, Archivum debe quedar disponible localmente con todos sus servicios principales activos.

El usuario debe poder acceder al backend, al frontend y a Prometheus sin ejecutar configuraciones manuales adicionales fuera de las indicadas en este documento.