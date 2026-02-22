# 01 · Visión General del Sistema

## 1. Objetivo del capítulo

Este documento describe la arquitectura global del sistema desarrollado, identificando sus principales componentes, las relaciones entre ellos y las decisiones técnicas adoptadas en su diseño.

El objetivo no es detallar la implementación interna de cada módulo, sino ofrecer una visión estructurada y comprensible del sistema desde un punto de vista conceptual y técnico.

La arquitectura se ha definido antes del inicio del desarrollo con el fin de:

- Garantizar coherencia con los requisitos funcionales (R01–R02)
- Reducir improvisaciones durante la implementación
- Facilitar la integración de componentes
- Asegurar la trazabilidad entre diseño y desarrollo

---

## 2. Descripción General del Sistema

El sistema desarrollado puede entenderse como una **plataforma de gestión documental enriquecida con capacidades de búsqueda semántica y generación de respuestas contextualizadas (RAG)**.

Desde una perspectiva de alto nivel, el sistema se compone de los siguientes bloques principales:

- Interfaz de usuario (frontend básico)
- API backend
- Sistema de almacenamiento documental
- Base de datos relacional con soporte vectorial
- Módulo de procesamiento de documentos
- Módulo de búsqueda semántica
- Flujo de generación de respuestas (RAG)

El usuario interactúa con el sistema a través de una interfaz que permite:

- Subir documentos
- Consultar información
- Ejecutar búsquedas
- Generar respuestas contextualizadas

Todas las peticiones son gestionadas por el backend, que actúa como núcleo de coordinación del sistema.

---

## 3. Responsabilidades del Backend

El backend concentra la lógica de negocio y el control del sistema. Sus principales responsabilidades son:

- Gestión de usuarios y autenticación
- Control de roles y permisos
- Orquestación del procesamiento documental
- Gestión de consultas semánticas
- Integración del flujo RAG

El backend evita el acceso directo a la base de datos, garantizando una arquitectura controlada y desacoplada.

---

## 4. Persistencia y Representación Vectorial

La base de datos cumple una doble función:

1. Almacenar información estructurada:
   - Usuarios
   - Documentos
   - Versiones
   - Metadata
   - Estados de procesamiento

2. Persistir representaciones vectoriales de los fragmentos de texto procesados (embeddings)

Esta unificación permite implementar búsquedas semánticas e híbridas sin necesidad de integrar motores externos adicionales.

---

## 5. Procesamiento en Segundo Plano

El procesamiento documental se ejecuta mediante un componente tipo *worker* que opera en segundo plano.

Este módulo se encarga de:

- Extracción de texto
- Fragmentación en chunks
- Generación de embeddings
- Actualización de estados de procesamiento

El diseño asíncrono evita bloquear las operaciones síncronas del backend y permite mantener trazabilidad del estado de cada trabajo.

---

## 6. Integración con Servicio Externo de IA

El servicio externo de IA se utiliza exclusivamente para:

- Generación de embeddings
- Generación de respuestas en el flujo RAG

Este servicio se mantiene desacoplado del dominio de la aplicación, evitando dependencias estructurales en la arquitectura interna.

---

## 7. Diagrama de Contexto (C4 Nivel Contexto)

**Figura 5.1 – Diagrama C4 Nivel Contexto**

Representa el sistema como una única entidad dentro de su entorno, mostrando:

- Interacción con el usuario
- Integración con el servicio externo de IA

Este nivel permite entender el alcance global del sistema antes de descomponerlo en contenedores.

---

## 8. Diagrama C4 Nivel Contenedor

**Figura 5.2 – Diagrama C4 Nivel Contenedor**

Descompone el sistema en sus principales contenedores desplegables:

- Frontend web
- Backend API
- Base de datos PostgreSQL con soporte vectorial
- Worker de procesamiento en segundo plano
- Redis (rate limiting)
- Prometheus (monitorización)
- Servicio externo de IA

El frontend actúa como cliente del backend mediante peticiones HTTPS en formato JSON.

Toda la lógica de negocio y el control de acceso se centralizan en el backend API, evitando el acceso directo a la base de datos.

Esta separación en contenedores desplegables facilita:

- Escalabilidad
- Mantenibilidad
- Reproducibilidad mediante Docker Compose