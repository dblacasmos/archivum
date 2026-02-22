# Arquitectura del Sistema (R03)

## 1. Propósito

Esta carpeta contiene la documentación técnica asociada al requisito **R03 – Arquitectura global del sistema**.

Aquí se recoge el diseño conceptual y lógico del sistema definido antes del desarrollo, con el objetivo de garantizar:

- Coherencia con los requisitos funcionales (R01–R02)
- Separación clara de responsabilidades
- Trazabilidad entre diseño y desarrollo
- Justificación técnica de las decisiones adoptadas

La documentación aquí incluida respalda el capítulo de Arquitectura de la memoria final.

---

## 2. Estructura

La arquitectura se ha dividido en documentos independientes para facilitar:

- Versionado en Git
- Mantenibilidad
- Claridad estructural

### Documentos incluidos

- **01_vision_general.md**  
  Descripción de alto nivel del sistema y sus bloques principales.

- **02_arquitectura_logica.md**  
  Modelo en capas y separación de responsabilidades.

- **03_componentes.md**  
  Identificación y descripción de los módulos funcionales.

- **04_datos_y_modelado.md**  
  Modelo de datos E/R y relaciones entre entidades.

- **05_decisiones_tecnicas.md**  
  Justificación tecnológica y alternativas descartadas.

- **06_secuencia_flujos.md**  
  Diagramas de secuencia y comportamiento dinámico del sistema.

- **07_seguridad.md**  
  Modelo de seguridad, autenticación y control de acceso.

---

## 3. Diagramas

Los archivos fuente de los diagramas (C4, arquitectura en capas, componentes, modelo E/R y secuencias) se encuentran en:

`docs/diagrams/`

En los documentos anteriores se incluyen las versiones exportadas de dichos diagramas, manteniendo:

- Separación entre contenido explicativo y artefactos gráficos
- Versionado independiente de los diagramas

---

## 4. Alcance

Esta documentación describe:

- Arquitectura conceptual
- Arquitectura lógica
- Arquitectura de componentes
- Modelo de datos
- Decisiones técnicas
- Flujos dinámicos
- Seguridad

No incluye:

- Implementación de código
- Manuales de usuario
- Procedimientos de despliegue
- Configuración de entorno

Estos aspectos se documentan en otras carpetas del proyecto.

---

## 5. Coherencia Global

La arquitectura definida en esta carpeta:

- Está alineada con la planificación inicial del proyecto
- Da soporte directo a los requisitos R10–R94
- Se implementa de forma coherente en el código fuente
- Permite evolución futura sin rediseño estructural

Esta carpeta constituye la base técnica del sistema y refleja el diseño previo al desarrollo.