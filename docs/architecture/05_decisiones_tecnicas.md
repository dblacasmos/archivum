# 05 · Decisiones Técnicas Adoptadas

## 1. Criterios de Selección Tecnológica

La selección tecnológica del proyecto se ha realizado atendiendo a los siguientes criterios:

- Coherencia con la arquitectura definida
- Viabilidad en un contexto académico individual
- Robustez técnica
- Alineación con tecnologías utilizadas en entornos profesionales actuales
- Equilibrio entre complejidad y mantenibilidad

No se ha priorizado la novedad tecnológica, sino la adecuación al alcance real del proyecto.

---

## 2. Backend y Arquitectura de Servicios

### Tecnología seleccionada:
- **Python + FastAPI**

### Justificación:

- Ecosistema sólido para procesamiento de texto e IA
- Desarrollo rápido y estructurado
- Validación automática de datos mediante modelos tipados
- Generación automática de documentación OpenAPI
- Modularidad natural para APIs REST

### Alternativa considerada:
- Java + Spring Boot

### Motivo de descarte:

- Mayor complejidad estructural
- Sobrecarga innecesaria para el alcance académico
- No aporta ventaja diferencial para este proyecto

---

## 3. Persistencia y Modelo de Datos

### Tecnología seleccionada:
- **PostgreSQL 16 + pgvector**

### Justificación:

- Robustez relacional
- Soporte transaccional sólido
- Extensibilidad mediante extensiones
- Unificación de datos estructurados y vectoriales en un único sistema

Esta decisión evita fragmentar la arquitectura en múltiples motores.

### Alternativas descartadas:

- MongoDB
- Motor vectorial externo

Motivo: añadirían complejidad y desacoplarían la trazabilidad entre documentos y embeddings.

---

## 4. ORM y Migraciones

### Tecnología seleccionada:
- **SQLAlchemy 2.0 + Alembic**

### Justificación:

- Control explícito del modelo de datos
- Migraciones versionadas
- Coherencia con arquitectura en capas
- Buen equilibrio entre control y productividad

Se descartó el acceso directo sin ORM por menor mantenibilidad.

---

## 5. Procesamiento Documental

### Tecnología seleccionada:
- **PyMuPDF + python-docx**

### Justificación:

- Extracción fiable de texto
- Ligereza
- Adecuado para PDF y documentos comunes

Se descartó OCR completo por introducir complejidad innecesaria.

---

## 6. Seguridad y Control de Acceso

### Enfoque adoptado:
- JWT (access + refresh)
- RBAC (Role-Based Access Control)

### Justificación:

- Arquitectura stateless
- Escalabilidad
- Separación clara entre autenticación y autorización
- Soporte de rotación y revocación de refresh tokens

Se descartaron sesiones en servidor por limitar escalabilidad y claridad arquitectónica.

Además, se aplica principio de mínimo privilegio en búsqueda semántica y RAG, filtrando resultados por propiedad del documento.

---

## 7. Pipeline Asíncrono

### Enfoque adoptado:
- Background tasks + tabla de seguimiento de estados

### Justificación:

- Simplicidad estructural
- No requiere infraestructura adicional
- Suficiente para el alcance del proyecto

Alternativa descartada:
- Celery + Redis como cola de tareas

Motivo: complejidad excesiva para un proyecto académico individual.

---

## 8. Rate Limiting

### Tecnología seleccionada:
- Redis

### Justificación:

- Operaciones atómicas rápidas
- No sobrecarga la base de datos principal
- Protección eficaz frente a abuso

Se aplica sobre endpoints críticos como:

- `/auth/login`
- `/query`
- `/documents/upload`

Se devuelve HTTP 429 cuando se supera el límite configurado.

---

## 9. Vectorización e Integración de IA

### Enfoque adoptado:
- Modelo accesible mediante API externa

### Justificación:

- Integración estable
- Documentación sólida
- Permite centrarse en arquitectura y control de contexto
- Evita gestionar infraestructura de modelos locales

Se descartó modelo autoalojado por aumentar significativamente la carga técnica.

---

## 10. Frontend

### Tecnología seleccionada:
- React + Vite

### Justificación:

- Ligero
- Suficiente para validación funcional
- Separación clara frontend/backend
- Rapidez de desarrollo

No se priorizó un framework SSR complejo por no aportar valor adicional al alcance del proyecto.

---

## 11. Contenerización y Despliegue

### Tecnología seleccionada:
- Docker Compose

### Justificación:

- Reproducibilidad
- Coherencia entre entornos
- Facilita evaluación por tribunal
- Alineación con prácticas DevOps actuales

Se descartó instalación manual por reducir profesionalidad y trazabilidad.

---

## 12. Testing y Control de Versiones

### Testing:
- pytest

Ecosistema consolidado en Python, adecuado para pruebas unitarias y funcionales.

### Control de versiones:
- Git + GitHub

Permite trazabilidad del desarrollo, versionado por requisitos y coherencia con metodología Kanban.

---

## 13. Observabilidad y Monitorización

Se incorporan:

- Logs estructurados en JSON
- request_id por petición
- Métricas de latencia
- Endpoint `/metrics` compatible con Prometheus

Este enfoque permite:

- Analizar comportamiento del sistema
- Medir rendimiento
- Facilitar depuración

Sin introducir plataformas externas complejas.

---

## 14. Coherencia Global

Las decisiones técnicas adoptadas reflejan un enfoque equilibrado entre:

- Solidez arquitectónica
- Viabilidad académica
- Mantenibilidad
- Escalabilidad futura

Cada elección responde a una necesidad concreta del sistema y se integra de forma coherente en la arquitectura global definida.