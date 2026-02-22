# 06 · Secuencia de Flujos del Sistema

## 1. Introducción

Este apartado describe los principales flujos dinámicos del sistema mediante diagramas de secuencia.

El objetivo es representar cómo interactúan los distintos componentes a lo largo del ciclo completo:

- Ingesta documental
- Búsqueda semántica
- Generación de respuestas (RAG)

Estos diagramas complementan la arquitectura estática mostrando el comportamiento en tiempo de ejecución.

---

# 2. Flujo de Ingesta Documental

**Figura X.X – Diagrama de Secuencia: Ingesta Documental**

## 2.1 Descripción General

El flujo comienza cuando un usuario autenticado sube un documento al sistema.

### Secuencia simplificada:

1. Usuario envía documento al frontend.
2. Frontend realiza petición HTTP al backend.
3. Backend:
   - Valida autenticación y permisos.
   - Persiste el documento.
   - Crea una nueva versión.
   - Registra estado inicial del procesamiento.
4. Se activa el pipeline asíncrono.
5. Worker:
   - Extrae texto.
   - Fragmenta en chunks.
   - Genera embeddings.
   - Persiste chunks y embeddings.
   - Actualiza estado del trabajo.

## 2.2 Características del diseño

- Procesamiento en segundo plano.
- No bloqueo del hilo principal.
- Trazabilidad de estados.
- Separación clara entre persistencia y procesamiento.

Este flujo da soporte a los requisitos R20–R32.

---

# 3. Flujo de Búsqueda Semántica

**Figura X.X – Diagrama de Secuencia: Búsqueda Semántica**

## 3.1 Descripción General

El flujo se inicia cuando el usuario realiza una consulta desde la interfaz.

### Secuencia simplificada:

1. Usuario introduce consulta.
2. Frontend envía petición al backend.
3. Backend:
   - Valida autenticación.
   - Genera embedding de la consulta.
   - Ejecuta consulta vectorial en PostgreSQL.
   - Aplica filtros por metadata.
   - Aplica restricciones por rol/propiedad.
4. Devuelve resultados ordenados por similitud.

## 3.2 Características del diseño

- Consulta híbrida posible (texto + vector).
- Filtrado de resultados por permisos.
- Separación entre cálculo de embedding y recuperación.
- Uso de índices vectoriales para eficiencia.

Este flujo se relaciona con R50–R54.

---

# 4. Flujo RAG (Retrieval-Augmented Generation)

**Figura X.X – Diagrama de Secuencia: Flujo RAG**

## 4.1 Descripción General

El flujo RAG amplía la búsqueda semántica incorporando generación de respuesta.

### Secuencia simplificada:

1. Usuario realiza una pregunta.
2. Backend ejecuta búsqueda semántica.
3. Se recuperan los fragmentos más relevantes.
4. Se construye un prompt contextualizado.
5. Se envía al modelo de lenguaje externo.
6. Se recibe respuesta generada.
7. Se asocian fuentes (citas).
8. Se devuelve respuesta al usuario.

## 4.2 Control de seguridad y coherencia

- Se respetan permisos del usuario.
- Solo se incluyen chunks autorizados.
- Se limita el contexto para reducir alucinaciones.
- Se registra evento y métricas de latencia.

Este flujo se relaciona con R70–R75.

---

# 5. Registro y Observabilidad

En cada uno de los flujos anteriores:

- Se genera request_id.
- Se registran logs estructurados.
- Se miden tiempos de ejecución.
- Se exponen métricas vía `/metrics`.

Esto permite analizar:

- Latencia por etapa (retrieval, embedding, LLM).
- Consumo aproximado.
- Comportamiento del sistema.

Refuerza la mantenibilidad y la evaluación del proyecto.

---

# 6. Coherencia Arquitectónica

Los flujos descritos demuestran:

- Separación clara entre módulos.
- Ausencia de dependencias circulares.
- Desacoplamiento entre procesamiento y consulta.
- Integración controlada del servicio externo de IA.

El comportamiento dinámico del sistema es coherente con la arquitectura lógica y física previamente definida.