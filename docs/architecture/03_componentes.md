# 03 · Componentes Principales del Sistema

## 1. Introducción

A partir de la arquitectura lógica en capas se identifican los principales componentes funcionales del sistema.

Estos módulos especializados colaboran entre sí para cubrir el ciclo completo de gestión documental inteligente, desde la subida de documentos hasta la generación de respuestas contextualizadas mediante RAG.

**Figura 5.4 – Diagrama de Componentes Principales del Sistema**

El diagrama representa los módulos funcionales identificados y sus relaciones principales, permitiendo visualizar el flujo de información y la separación de responsabilidades dentro de la plataforma.

---

## 2. Módulo de Gestión de Usuarios

Responsable de la seguridad y control de acceso del sistema.

Funciones principales:

- Autenticación mediante JWT (access + refresh)
- Validación de tokens
- Rotación y revocación de refresh tokens
- Control de acceso basado en roles (RBAC)

Este módulo proporciona una capa transversal de seguridad que garantiza que únicamente los usuarios autorizados puedan acceder a los recursos y endpoints sensibles.

Se integra directamente con los requisitos R10, R11 y R12.

---

## 3. Módulo de Gestión Documental

Constituye la base funcional del sistema.

Responsabilidades:

- Subida de documentos
- Versionado
- Asociación de metadata
- Persistencia estructurada

Este componente sirve como punto de entrada al pipeline de procesamiento posterior y mantiene la trazabilidad entre documento, versión y usuario propietario.

Se relaciona con los requisitos R20–R22.

---

## 4. Módulo de Procesamiento

Encargado de transformar documentos en información preparada para su análisis semántico.

Incluye:

- Extracción de texto
- Fragmentación en chunks
- Orquestación asíncrona del pipeline
- Gestión de estados de procesamiento

El procesamiento se ejecuta en segundo plano mediante un worker, evitando bloquear operaciones síncronas del backend.

Este módulo da soporte a los requisitos R30–R32.

---

## 5. Módulo de Vectorización

Responsable de convertir los fragmentos de texto en representaciones vectoriales.

Funciones:

- Generación de embeddings
- Asociación embedding–chunk
- Persistencia en PostgreSQL con pgvector

Permite representar el contenido en un espacio semántico, haciendo posible la recuperación basada en similitud.

Se relaciona con los requisitos R40–R42.

---

## 6. Módulo de Búsqueda

Actúa como punto central de recuperación de información estructurada y vectorial.

Incluye:

- Consulta semántica
- Búsqueda híbrida (texto + vector)
- Filtros por metadata
- Restricciones de acceso por documento

En esta versión, el control de acceso se aplica por propiedad (owner), garantizando que solo se recuperan fragmentos pertenecientes a documentos autorizados para el usuario autenticado.

Modelos más avanzados (ACL, multi-tenant) se contemplan como posibles ampliaciones futuras.

Se vincula con los requisitos R50–R54.

---

## 7. Módulo RAG (Retrieval-Augmented Generation)

Coordina la generación de respuestas contextualizadas.

Responsabilidades:

- Recuperación de fragmentos relevantes
- Construcción del contexto
- Generación de respuesta mediante modelo de lenguaje

Este módulo se apoya en el sistema de búsqueda sin sustituirlo, reforzando el diseño modular.

No modifica la estructura base del sistema, sino que la amplía.

Se relaciona con los requisitos R70–R75.

---

## 8. Infraestructura Transversal

Además de los módulos funcionales, el sistema incorpora componentes transversales:

- Observabilidad (logs estructurados + métricas)
- Rate limiting mediante Redis
- Monitorización compatible con Prometheus

Estos elementos no forman parte directa del dominio funcional, pero refuerzan:

- Seguridad
- Estabilidad
- Trazabilidad
- Mantenibilidad

Se alinean con los requisitos R14 y R15.

---

## 9. Flujo General de Información

De forma simplificada, el flujo del sistema es el siguiente:

1. El usuario sube un documento.
2. El módulo documental lo persiste.
3. El módulo de procesamiento extrae y fragmenta el contenido.
4. El módulo de vectorización genera embeddings.
5. El módulo de búsqueda permite recuperar fragmentos.
6. El módulo RAG genera respuestas contextualizadas.
7. El sistema registra eventos y métricas.

Este flujo evidencia la cooperación entre módulos especializados, manteniendo separación de responsabilidades y coherencia arquitectónica.