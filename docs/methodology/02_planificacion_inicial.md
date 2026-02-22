# 02 · Planificación Inicial del Proyecto

## 1. Introducción

La planificación inicial del proyecto se elaboró antes del inicio del desarrollo con el objetivo de:

- Estimar el esfuerzo total requerido.
- Organizar el trabajo por bloques funcionales.
- Identificar dependencias entre requisitos.
- Establecer una referencia para el seguimiento posterior.

Esta planificación constituye una **estimación inicial**, no un registro de ejecución real.  
El análisis de desviaciones se documenta en un apartado independiente :contentReference[oaicite:1]{index=1}.

---

## 2. Enfoque de Planificación

La planificación se estructura en torno a los requisitos definidos en R01–R94.

Cada requisito incluye:

- Identificador (RXX)
- Descripción funcional
- Estimación de horas
- Clasificación por fase
- Labels técnicos (desarrollo, pruebas, documentación, infra, IA, etc.)

El trabajo se organiza en fases que reflejan la evolución lógica del sistema.

---

# 3. Distribución por Fases

## Fase 0 – Preparación (24 h)

Incluye definición conceptual del proyecto:

- R01 – Definición del problema y objetivos
- R02 – Alcance, exclusiones y supuestos
- R03 – Arquitectura global
- R04 – Metodología y planificación
- R05 – Identificación de riesgos

**Subtotal Fase 0: 24 horas** :contentReference[oaicite:2]{index=2}

---

## Fase 1 – Backend Core (111 h)

Bloque principal del sistema.

### Seguridad y Usuarios
- R10 – Modelo de usuarios
- R11 – Autenticación JWT + refresh tokens
- R12 – RBAC + permisos por documento
- R13 – Tests de seguridad
- R14 – Rate limiting
- R15 – Observabilidad

### Gestión Documental
- R20 – Subida de documentos
- R21 – Metadata
- R22 – Versionado
- R23 – Tests documentales

### Ingesta y Procesamiento
- R30 – Extracción de texto
- R31 – Chunking
- R32 – Pipeline asíncrono
- R33 – Tests pipeline

### Vectorización
- R40 – Generación de embeddings
- R41 – Almacenamiento pgvector
- R42 – Índices vectoriales
- R43 – Tests vectoriales

**Subtotal Fase 1: 111 horas** :contentReference[oaicite:3]{index=3}

---

## Fase 2 – Búsqueda Semántica (38 h)

- R50 – Búsqueda semántica básica
- R51 – Búsqueda híbrida
- R52 – Ranking explicable
- R53 – Filtros por metadata
- R54 – Seguridad por documento en retrieval
- R55 – Tests de búsqueda
- R56 – Front básico de búsqueda

**Subtotal Fase 2: 38 horas** :contentReference[oaicite:4]{index=4}

---

## Fase 3 – RAG + IA (34 h)

- R70 – Implementación RAG básica
- R71 – Control de alucinaciones
- R72 – Sistema de citas
- R73 – Evaluación automática
- R74 – Métricas latencia / coste
- R75 – Tests IA

**Subtotal Fase 3: 34 horas** :contentReference[oaicite:5]{index=5}

---

## Fase 4 – Data & Analytics (14 h)

- R80 – Tracking de eventos
- R82 – Dashboard Power BI

**Subtotal Fase 4: 14 horas** :contentReference[oaicite:6]{index=6}


---

## Fase 5 – Cierre (22 h)

- R90 – Docker Compose
- R91 – Script de despliegue
- R92 – Manual de instalación
- R93 – Manual de usuario
- R94 – Preparación defensa

**Subtotal Fase 5: 22 horas** :contentReference[oaicite:7]{index=7}

---

# 4. Estimación Temporal Total

| Fase | Horas |
|------|-------|
| Fase 0 – Preparación | 24 h |
| Fase 1 – Backend Core | 111 h |
| Fase 2 – Búsqueda Semántica | 38 h |
| Fase 3 – RAG + IA | 34 h |
| Fase 4 – Analytics | 14 h |
| Fase 5 – Cierre | 22 h |
| **Total Proyecto** | **235 h** |

Estimación total del proyecto: **235 horas** :contentReference[oaicite:8]{index=8}.

---

# 5. Justificación de la Distribución

La mayor carga de trabajo se concentra en:

- Backend Core
- Búsqueda Semántica
- Integración de IA

Estas fases presentan mayor complejidad técnica y requieren:

- Diseño estructural
- Implementación progresiva
- Validación funcional

Las fases iniciales y finales presentan menor carga horaria, aunque son relevantes desde el punto de vista metodológico y académico.

La estimación propuesta busca ser realista y coherente con el alcance del proyecto y el nivel formativo del ciclo :contentReference[oaicite:9]{index=9}.

---

# 6. Rol de la Planificación

La planificación inicial no se considera rígida ni inmutable.

Su función es:

- Servir como marco de referencia.
- Facilitar el seguimiento posterior.
- Permitir análisis objetivo de desviaciones.

El contraste entre planificación prevista y ejecución real se documenta en el apartado correspondiente de seguimiento del proyecto.