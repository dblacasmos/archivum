# 07 · Seguridad y Control de Acceso

## 1. Enfoque General de Seguridad

La arquitectura del sistema incorpora un modelo de seguridad basado en los siguientes principios:

- Arquitectura stateless
- Autenticación mediante tokens JWT
- Control de acceso basado en roles (RBAC)
- Principio de mínimo privilegio
- Protección frente a abuso mediante rate limiting
- Registro y trazabilidad de acciones

El objetivo no es implementar un sistema de seguridad empresarial completo, sino garantizar un nivel sólido y coherente con el alcance del proyecto.

---

## 2. Autenticación basada en JWT

La autenticación se implementa mediante:

- Access Token (vida corta: 10–20 minutos)
- Refresh Token (vida más larga: 7–30 días)

### 2.1 Access Token

Se utiliza para:

- Acceder a endpoints protegidos
- Validar identidad del usuario
- Aplicar control de acceso por rol

Ventajas:

- Arquitectura stateless
- No requiere sesión en servidor
- Escalable

### 2.2 Refresh Token

Permite:

- Renovar access tokens sin login completo
- Mantener sesiones persistentes

Características de seguridad:

- Almacenado en base de datos como hash
- Estado gestionado (activo, revocado, reemplazado, expirado)
- Rotación automática en cada uso válido
- Posibilidad de revocación (logout o sospecha)

Este modelo refuerza la seguridad sin introducir estado en memoria del servidor.

---

## 3. Control de Acceso Basado en Roles (RBAC)

El sistema implementa RBAC (Role-Based Access Control).

Cada usuario:

- Está asociado a uno o varios roles.
- Solo puede acceder a endpoints permitidos por su rol.

El control se aplica en:

- Endpoints administrativos
- Gestión documental
- Búsqueda y recuperación de información

Esto permite:

- Separación de permisos
- Control granular
- Escalabilidad del modelo de seguridad

---

## 4. Principio de Mínimo Privilegio

Además del RBAC, se aplica control por propiedad del documento.

En el contexto de:

- Búsqueda semántica
- Flujo RAG

Solo se recuperan:

- Fragmentos pertenecientes a documentos autorizados para el usuario autenticado.

Esto evita:

- Filtraciones accidentales
- Acceso cruzado no permitido
- Exposición indebida de información

Modelos más avanzados (ACL, multi-tenant) se contemplan como ampliaciones futuras.

---

## 5. Protección frente a Abuso (Rate Limiting)

Para mitigar:

- Ataques de fuerza bruta
- Uso abusivo de recursos
- Saturación del sistema

Se implementa rate limiting mediante Redis.

Se aplica especialmente en:

- `/auth/login`
- `/query`
- `/documents/upload`

Cuando se supera el umbral configurado:

- Se devuelve HTTP 429 (Too Many Requests).

Redis se utiliza como backend de contadores rápidos y atómicos, evitando sobrecargar la base de datos principal.

---

## 6. Observabilidad y Registro de Eventos

La seguridad se refuerza mediante:

- Logs estructurados en formato JSON
- Inclusión de:
  - request_id
  - user_id (si aplica)
  - endpoint
  - status_code
  - latencia

Además, el sistema expone:

- Endpoint `/metrics` compatible con Prometheus.

Esto permite:

- Detectar comportamientos anómalos
- Analizar patrones de uso
- Medir tiempos de respuesta
- Evaluar posibles abusos

---

## 7. Seguridad en el Flujo RAG

En el flujo de generación de respuestas:

- Se filtran previamente los fragmentos según permisos.
- Se limita el contexto enviado al modelo.
- Se evita incluir información no autorizada.

El modelo de lenguaje externo no tiene acceso directo a la base de datos ni a la lógica interna del sistema, manteniéndose desacoplado.

---

## 8. Coherencia con la Arquitectura Global

El diseño de seguridad:

- Está integrado transversalmente en la arquitectura.
- No depende de soluciones externas complejas.
- Mantiene separación clara entre autenticación, autorización y dominio.
- Refuerza la robustez sin introducir sobreingeniería.

Este enfoque garantiza un equilibrio entre seguridad, mantenibilidad y viabilidad académica.