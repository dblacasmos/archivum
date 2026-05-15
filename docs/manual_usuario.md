# Manual de usuario de Archivum

Este documento describe el uso básico del sistema Archivum desde el punto de vista del usuario final.

El objetivo del manual es facilitar la validación funcional del sistema mostrando cómo utilizar las principales funcionalidades implementadas durante el desarrollo del proyecto.

---

# 1. Acceso al sistema

Archivum se ejecuta localmente mediante Docker Compose.

Una vez iniciado el sistema, los servicios principales quedan accesibles desde el navegador.

## URLs principales

| Servicio | URL |
|---|---|
| Frontend | http://localhost |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Prometheus | http://localhost:9090 |

---

# 2. Inicio de sesión

La autenticación del sistema se realiza mediante JWT.

El usuario debe autenticarse desde Swagger para obtener un token válido.

## Pasos de autenticación

### Paso 1

Acceder a Swagger:

```text
http://localhost:8000/docs
```

Explicación sencilla:

- `http://localhost:8000`
  indica que el backend se ejecuta en el ordenador local.

- `/docs`
  abre Swagger UI, que permite probar la API desde el navegador.

---

### Paso 2

Abrir el endpoint:

```text
POST /auth/login
```

Explicación sencilla:

- `POST`
  significa que se envían datos al servidor.

- `/auth/login`
  es el endpoint encargado de autenticar usuarios.

---

### Paso 3

Introducir las credenciales del usuario:

```json
{
  "email": "admin@archivum.local",
  "password": "admin123"
}
```

Explicación sencilla:

- `"email"`
  identifica al usuario.

- `"password"`
  contiene la contraseña del usuario.

- El backend valida ambos datos antes de generar el token JWT.

---

### Paso 4

Copiar el token JWT recibido en la respuesta.

Ejemplo:

```text
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

Explicación sencilla:

- El token JWT representa la sesión autenticada.

- El frontend y Swagger utilizan este token para acceder a endpoints protegidos.

- Si el token no existe o es inválido, el backend devuelve error `401 Unauthorized`.

---

### Paso 5

Pulsar el botón `Authorize` en Swagger e introducir:

```text
Bearer TU_TOKEN
```

Explicación sencilla:

- `Bearer`
  indica el tipo de autenticación.

- `TU_TOKEN`
  debe sustituirse por el JWT generado anteriormente.

- Swagger añadirá automáticamente el token a las peticiones siguientes.

---

# 3. Subida de documentos

Archivum permite subir documentos para su posterior procesamiento semántico.

## Endpoint utilizado

```text
POST /documents/upload
```

Explicación sencilla:

- Este endpoint recibe archivos enviados por el usuario.

- El documento se almacena en el sistema y queda asociado al usuario autenticado.

---

## Pasos para subir un documento

### Paso 1

Abrir el endpoint:

```text
POST /documents/upload
```

---

### Paso 2

Pulsar el botón `Choose File`.

---

### Paso 3

Seleccionar un documento PDF o TXT.

---

### Paso 4

Ejecutar la petición pulsando `Execute`.

---

## Resultado esperado

El sistema devolverá una respuesta similar a:

```json
{
  "message": "Documento subido correctamente",
  "document_id": "8d71d7c1"
}
```

Explicación sencilla:

- `"message"`
  indica si la operación se realizó correctamente.

- `"document_id"`
  identifica el documento almacenado en el sistema.

- Este identificador se utiliza posteriormente en procesamiento y búsqueda.

---

# 4. Procesamiento documental

Una vez subido el documento, Archivum ejecuta automáticamente el pipeline documental.

El pipeline realiza:

- extracción de texto
- chunking
- generación de embeddings
- almacenamiento vectorial

---

## Resultado esperado

El documento queda preparado para:

- búsqueda semántica
- búsqueda híbrida
- consultas RAG

Porque aparentemente ya no basta con guardar PDFs. Ahora también hay que convertirlos en vectores matemáticos para que una IA finja comprenderlos. Evolución tecnológica completamente normal.

---

# 5. Búsqueda semántica

Archivum permite realizar búsquedas semánticas utilizando embeddings.

## Endpoint utilizado

```text
POST /query
```

---

## Ejemplo de consulta

```json
{
  "query": "contrato laboral",
  "limit": 3
}
```

Explicación sencilla:

- `"query"`
  contiene el texto que desea buscar el usuario.

- `"limit"`
  indica el número máximo de resultados.

---

## Resultado esperado

```json
{
  "results": [
    {
      "document_name": "Contrato legal autorizado",
      "score": 0.91
    }
  ]
}
```

Explicación sencilla:

- `"document_name"`
  indica el documento recuperado.

- `"score"`
  representa la relevancia del resultado.

- Cuanto mayor es el score, más relevante considera el sistema ese resultado.

---

# 6. Búsqueda híbrida

Archivum combina búsqueda textual y búsqueda semántica.

Esto permite mejorar la relevancia de los resultados recuperados.

---

## Ejemplo de consulta híbrida

```json
{
  "query": "contrato laboral",
  "limit": 5,
  "metadata_filters": {
    "category": "legal"
  }
}
```

Explicación sencilla:

- `"metadata_filters"`
  aplica filtros sobre la metadata documental.

- `"category": "legal"`
  limita los resultados a documentos legales.

- El sistema combina similitud vectorial y coincidencia textual.

---

# 7. Frontend de búsqueda

Archivum incluye un frontend básico para validar funcionalmente el sistema.

El frontend permite:

- introducir consultas
- visualizar resultados
- aplicar filtros simples
- consultar ranking explicable

---

## Flujo básico de uso

### Paso 1

Acceder al frontend:

```text
http://localhost
```

---

### Paso 2

Introducir una consulta en el cuadro de búsqueda.

---

### Paso 3

Pulsar el botón `Buscar`.

---

### Paso 4

Visualizar los resultados recuperados.

---

# 8. Consultas RAG

Archivum incorpora un flujo RAG básico para generar respuestas utilizando contexto documental recuperado.

## Endpoint utilizado

```text
POST /rag
```

---

## Ejemplo de consulta RAG

```json
{
  "query": "¿Qué indica el contrato sobre vacaciones?"
}
```

Explicación sencilla:

- El sistema recupera chunks relevantes.

- Los chunks se utilizan como contexto para el modelo de lenguaje.

- El modelo genera una respuesta basada en los documentos recuperados.

---

## Resultado esperado

```json
{
  "answer": "El contrato establece 30 días naturales de vacaciones.",
  "citations": [
    {
      "document_name": "Contrato legal autorizado"
    }
  ]
}
```

Explicación sencilla:

- `"answer"`
  contiene la respuesta generada.

- `"citations"`
  muestra las fuentes utilizadas.

- El sistema incluye trazabilidad básica entre respuesta y documentos.

---

# 9. Evaluación automática y métricas

Archivum registra métricas básicas relacionadas con:

- latencia
- tiempo de retrieval
- tiempo de generación
- coste aproximado
- evaluación automática

---

## Ejemplo de métricas

```json
{
  "usage_metrics": {
    "total_latency_ms": 1240,
    "retrieval_latency_ms": 140,
    "llm_latency_ms": 980
  }
}
```

Explicación sencilla:

- `"total_latency_ms"`
  representa el tiempo total de respuesta.

- `"retrieval_latency_ms"`
  mide el tiempo de recuperación documental.

- `"llm_latency_ms"`
  mide el tiempo empleado por el modelo de lenguaje.

---

# 10. Tracking de eventos

Archivum registra eventos básicos del sistema para análisis posterior.

Entre ellos:

- búsquedas
- consultas RAG
- documentos procesados
- errores básicos

---

# 11. Dashboard Power BI

Los eventos registrados pueden visualizarse posteriormente mediante Power BI.

El dashboard incluye:

- consultas realizadas
- volumen de documentos
- uso del sistema
- métricas básicas

---

# 12. Conclusión

El sistema Archivum permite gestionar documentos, procesarlos semánticamente y realizar consultas avanzadas mediante técnicas RAG y búsqueda híbrida.

El manual presentado tiene como objetivo facilitar la validación funcional del sistema, mostrando el flujo básico de uso desde la autenticación hasta la generación de respuestas basadas en contexto documental.