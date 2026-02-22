# 01 · Metodología de Trabajo (R04)

## 1. Enfoque General

El desarrollo del proyecto se ha planteado siguiendo un enfoque **iterativo e incremental**, estructurado en torno a requisitos claramente definidos.

En lugar de abordar el sistema como un bloque monolítico, el proyecto se divide en unidades de trabajo coherentes que permiten avanzar de forma progresiva y controlada.

Cada requisito:

- Define una unidad funcional completa.
- Tiene un objetivo concreto.
- Presenta un alcance delimitado.
- Incluye criterios explícitos de finalización.

Este enfoque permite reducir la complejidad del desarrollo y facilitar la validación independiente de cada bloque, manteniendo al mismo tiempo una visión global del sistema :contentReference[oaicite:1]{index=1}.


---

## 2. Justificación de la Metodología

La metodología adoptada prioriza:

- Trazabilidad
- Control
- Documentación continua
- Evaluación objetiva

En un contexto académico, no solo es necesario desarrollar funcionalidades, sino justificar:

- Qué se ha hecho.
- Por qué se ha hecho.
- Cómo se ha organizado el trabajo.

Por este motivo, se opta por un modelo que facilita la documentación estructurada del proceso y la alineación entre planificación y ejecución :contentReference[oaicite:2]{index=2}.

Asimismo, el enfoque seleccionado permite adaptar el ritmo de trabajo a la complejidad real de cada requisito, evitando estructuras temporales rígidas que no siempre se ajustan al desarrollo individual.


---

## 3. Uso de Kanban

Para la gestión del trabajo se ha adoptado **Kanban** como metodología de organización y seguimiento.

### 3.1 Motivos de elección

Kanban resulta adecuado para un proyecto individual por las siguientes razones:

- Visualización clara del estado de cada requisito.
- Flujo continuo de trabajo.
- Ausencia de iteraciones temporales rígidas.
- Flexibilidad ante variaciones de carga.

El tablero Kanban se estructura en columnas que representan estados como:

- Backlog
- Pendiente
- En curso
- Revisión
- Finalizado

Este modelo permite identificar bloqueos de forma temprana y mantener control sobre el avance real del proyecto :contentReference[oaicite:3]{index=3}.

### 3.2 Adecuación al contexto académico

A diferencia de metodologías basadas en sprints cerrados, Kanban no impone ciclos temporales estrictos, lo que facilita su adaptación a:

- Desarrollo individual.
- Variabilidad en la duración de tareas.
- Necesidad de aprendizaje autónomo.

Además, su integración con el repositorio de código permite asociar requisitos con commits y evidencias de desarrollo, reforzando la trazabilidad del proyecto :contentReference[oaicite:4]{index=4}.


---

## 4. Modelo RFTP Aplicado

Con el objetivo de estructurar el trabajo de forma clara y trazable, se adopta el modelo **RFTP**, que organiza el proyecto en cuatro niveles:

- **R** – Requisitos  
- **F** – Funciones  
- **T** – Tareas  
- **P** – Pruebas  

### 4.1 Aplicación práctica

En este proyecto:

- Los **requisitos (R)** constituyen la unidad principal de planificación y seguimiento.
- Cada requisito puede descomponerse internamente en:
  - Funciones (F)
  - Tareas técnicas (T)
  - Pruebas asociadas (P)

No obstante, únicamente los requisitos se gestionan directamente en el tablero Kanban, manteniendo una visión de alto nivel sin fragmentar excesivamente la planificación :contentReference[oaicite:5]{index=5}.

### 4.2 Trazabilidad

El modelo RFTP permite:

- Relacionar objetivos iniciales con evidencias de desarrollo.
- Vincular requisitos con commits.
- Asociar pruebas automatizadas.
- Justificar el cumplimiento funcional de cada bloque.

Los requisitos conceptuales (R01–R05) se estructuran principalmente a nivel de requisito, mientras que los requisitos técnicos (R10 en adelante) incluyen descomposición explícita en funciones, tareas y pruebas verificables :contentReference[oaicite:6]{index=6}.


---

## 5. Planificación Inicial por Requisitos

La planificación inicial del proyecto se organiza por fases funcionales:

- Fase 0 – Preparación
- Fase 1 – Backend Core
- Fase 2 – Búsqueda Semántica
- Fase 3 – RAG + IA
- Fase 4 – Data & Analytics
- Fase 5 – Cierre

Cada requisito cuenta con:

- Estimación temporal.
- Clasificación funcional mediante labels.
- Ubicación dentro de una fase concreta.

La estimación total del proyecto asciende a **235 horas**, distribuidas entre análisis, desarrollo, pruebas, documentación y cierre :contentReference[oaicite:7]{index=7}.

Esta planificación se define como una **estimación inicial**, utilizada como referencia para el seguimiento y análisis de desviaciones posterior.


---

## 6. Conclusión Metodológica

La combinación de:

- Kanban como metodología de gestión visual.
- Modelo RFTP como estructura interna de trabajo.
- Planificación por fases y requisitos.

Permite abordar el proyecto de forma:

- Ordenada
- Controlada
- Trazable
- Evaluable

Este enfoque metodológico constituye la base organizativa sobre la que se desarrolla el resto del sistema.