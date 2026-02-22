# 04 · Diseño de Datos y Modelado

## 1. Enfoque General

El diseño de datos se ha planteado siguiendo un modelo relacional extendido con capacidades vectoriales.

El objetivo es:

- Mantener coherencia estructural
- Garantizar integridad referencial
- Permitir trazabilidad completa desde documento hasta respuesta generada
- Integrar almacenamiento estructurado y vectorial en un único sistema

Se utiliza PostgreSQL como base de datos relacional, complementada con la extensión pgvector para el almacenamiento de embeddings.

---

## 2. Entidades Principales

Las entidades principales del sistema son:

- Usuario
- Rol
- Documento
- Versión
- Metadata
- Chunk
- Embedding
- Evento (tracking)
- Refresh_Token

Estas entidades permiten modelar tanto la gestión documental tradicional como el flujo semántico necesario para búsqueda y RAG.

---

## 3. Modelo de Datos E/R

**Figura 5.5 – Diagrama de Modelo de Datos E/R**

El diagrama representa las entidades principales del sistema y las relaciones existentes entre ellas.

Relaciones relevantes:

- Usuario (1:N) Documento
- Documento (1:N) Versión
- Versión (1:N) Chunk
- Chunk (1:1) Embedding
- Usuario (1:N) Refresh_Token
- Usuario (1:N) Evento

Esta estructura permite mantener trazabilidad completa desde:

Respuesta generada → Chunk → Versión → Documento → Usuario propietario

---

## 4. Gestión Documental y Versionado

El modelo establece una separación clara entre Documento y Versión:

- Documento representa la entidad lógica principal.
- Versión permite mantener histórico de cambios.

Cada versión puede tener múltiples chunks asociados tras el procesamiento.

Esto permite:

- Reprocesar versiones independientes
- Mantener coherencia histórica
- Evitar pérdida de información

---

## 5. Fragmentación y Representación Vectorial

Cada Versión genera múltiples Chunks tras el proceso de fragmentación.

Cada Chunk mantiene una correspondencia uno a uno con su Embedding vectorial.

Este diseño permite:

- Consultas por similitud vectorial
- Mantenimiento de trazabilidad
- Separación entre texto original y representación semántica

La representación vectorial se almacena en PostgreSQL mediante pgvector, evitando la necesidad de motores externos.

---

## 6. Gestión de Seguridad y Sesiones

Se incorpora la entidad Refresh_Token asociada a Usuario (1:N).

Características del diseño:

- Almacenamiento seguro mediante hash
- Estado del token (activo, revocado, reemplazado, expirado)
- Soporte para rotación de tokens

Este modelo permite sesiones persistentes sin mantener estado en memoria del servidor.

---

## 7. Tracking y Observabilidad

La entidad Evento permite registrar:

- Acciones del usuario
- Consultas realizadas
- Métricas relevantes

Este diseño facilita:

- Análisis posterior
- Construcción de dashboard analítico (R82)
- Evaluación del uso del sistema

El tracking está desacoplado del dominio principal, manteniendo el modelo limpio.

---

## 8. Separación Estructurada vs Vectorial

El diseño distingue claramente entre:

Información estructurada:
- Usuarios
- Documentos
- Metadata
- Estados

Representación vectorial:
- Embeddings asociados a chunks

Esta separación permite:

- Escalabilidad
- Evolución futura
- Integración de nuevos modelos de embeddings sin modificar el dominio relacional

Se mantiene así un modelo relacional coherente extendido con capacidades semánticas.

---

## 9. Coherencia con la Arquitectura

El modelo de datos definido:

- Se alinea con la arquitectura lógica en capas
- Da soporte a los módulos funcionales
- Permite trazabilidad completa del flujo RAG
- Facilita la implementación de búsqueda híbrida

No introduce dependencias innecesarias ni fragmentación en múltiples sistemas de persistencia.