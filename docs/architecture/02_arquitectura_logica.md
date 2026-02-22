# 02 · Arquitectura Lógica

## 1. Enfoque General

La arquitectura lógica del sistema se ha diseñado siguiendo un modelo en capas, con el objetivo de:

- Separar responsabilidades
- Reducir acoplamientos innecesarios
- Facilitar el mantenimiento y la evolución del sistema
- Asegurar coherencia estructural

Este enfoque permite aislar cambios en una capa sin impactar directamente en las demás, mejorando la claridad del diseño y la sostenibilidad del proyecto.

---

## 2. Modelo en Capas

La organización lógica del sistema se estructura en las siguientes capas:

- Capa de presentación
- Capa de aplicación o servicios
- Capa de dominio
- Capa de persistencia

**Figura 5.3 – Diagrama de Arquitectura Lógica en Capas**

Representa la organización interna del backend y la separación de responsabilidades.

---

## 3. Capa de Presentación

Responsable de la interacción con el usuario.

Incluye:

- Interfaz básica de búsqueda
- Gestión documental desde el frontend
- Envío de peticiones HTTP al backend

Su función es:

- Recoger solicitudes del usuario
- Mostrar resultados
- No incorporar lógica de negocio compleja

Toda la lógica relevante se delega en las capas inferiores.

---

## 4. Capa de Aplicación o Servicios

Contiene la lógica principal del sistema.

En esta capa se gestionan:

- Casos de uso
- Coordinación entre módulos
- Validación de reglas de negocio
- Orquestación del pipeline documental
- Flujo de búsqueda y RAG

Actúa como intermediaria entre la capa de presentación y la capa de dominio/persistencia.

Su responsabilidad es asegurar que el sistema responde conforme a los requisitos funcionales definidos.

---

## 5. Capa de Dominio

Define las entidades principales del sistema y sus relaciones conceptuales.

Incluye modelos como:

- Usuario
- Rol
- Documento
- Versión
- Metadata
- Chunk
- Embedding
- Evento (tracking)
- Refresh_Token

Esta capa representa el núcleo conceptual del sistema, independiente de detalles técnicos concretos como el framework o la base de datos.

El objetivo es mantener un modelo claro y coherente que refleje el problema de negocio.

---

## 6. Capa de Persistencia

Gestiona el acceso a la base de datos, incluyendo:

- Almacenamiento relacional tradicional
- Almacenamiento vectorial mediante pgvector
- Gestión de consultas estructuradas
- Gestión de consultas semánticas

Se encarga de:

- Mapear entidades del dominio a estructuras persistentes
- Mantener consistencia transaccional
- Garantizar integridad de los datos

La separación respecto a la capa de aplicación evita dependencias directas del motor de base de datos en la lógica de negocio.

---

## 7. Beneficios del Diseño en Capas

Este modelo permite cumplir el principio de separación de responsabilidades y aporta las siguientes ventajas:

- Mayor claridad estructural
- Reducción del acoplamiento
- Facilidad de mantenimiento
- Evolución futura del sistema sin rediseños profundos
- Evita dependencias circulares

Además, la arquitectura lógica es coherente con la arquitectura física descrita en los diagramas C4 (contexto y contenedores), asegurando alineación entre diseño conceptual y despliegue real.

---

## 8. Relación con los Requisitos

La arquitectura lógica definida da soporte directo a:

- R10–R13 (seguridad y usuarios)
- R20–R23 (gestión documental)
- R30–R33 (procesamiento)
- R40–R43 (vectorización)
- R50–R56 (búsqueda)
- R70–R75 (flujo RAG)

Cada bloque funcional se apoya en la separación en capas para mantener coherencia y trazabilidad entre diseño y desarrollo.