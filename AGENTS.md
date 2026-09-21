# AGENTS.md

Guía de este repositorio para cualquier agente que trabaje en él, humano o automático. Léela entera antes de tocar nada.

---

## 1. Qué es este proyecto

Un sistema **autónomo** de generación de novelas largas. Caso de referencia: épica deportiva. El sistema planifica, escribe, verifica, corrige, arbitra y cierra una novela completa **sin intervención externa en ningún punto del ciclo**.

Dos restricciones fijan todo el diseño:

- **Autonomía de extremo a extremo.** No hay aprobación manual, ni revisión de una persona, ni escalado. Cada decisión necesita una regla de precedencia, un umbral numérico o un agente responsable.
- **Ventana de contexto de 100.000 tokens** por llamada, entrada más salida, para cualquier agente.

La idea central del dominio: **una novela larga no es un texto largo, es un estado del mundo que evoluciona**. El texto es la proyección visible. El sistema gestiona el estado; la prosa es consecuencia.

---

## 2. Estado actual

| Fase | Estado |
|---|---|
| Ontología del dominio | ✅ Completa |
| Modelos y diagramas | ✅ Completos |
| Arquitectura, agentes y skills | ✅ Especificados |
| Catálogo de validaciones | ✅ Completo |
| Implementación de agentes | ⛔ **No iniciada** |
| Implementación de skills | ⛔ No iniciada |
| Capa de memoria | ⛔ No iniciada |

**El repositorio está en fase de especificación.** No hay código. No crees agentes, skills ni esqueletos de implementación salvo que se pida de forma explícita.

---

## 3. Estructura del repositorio

Es un **monorepo**: backend y frontend viven en la misma raíz, junto a la especificación.

```
.
├── AGENTS.md                 ← estás aquí: guía de trabajo e índice
├── CLAUDE.md                 ← instrucciones operativas para Claude Code
├── docs/
│   ├── definitions.md        ← ontología: qué existe en el dominio
│   ├── domain-knowledge.md   ← modelos visuales de esa ontología
│   ├── architecture.md       ← cómo se construye el sistema
│   └── validations.md        ← qué se valida y con qué regla
├── backend/                  ← API y motor del sistema autónomo
└── frontend/                 ← visualización del estado narrativo
```

`backend/` y `frontend/` existen pero están **vacías**: solo contienen un `.gitkeep`, porque git no versiona directorios sin ficheros. Reservan el sitio y fijan el stack; el contenido llega cuando arranque la implementación (§2).

### 3.1 Stack por carpeta

| Carpeta | Stack | Responsabilidad |
|---|---|---|
| `backend/` | Python + FastAPI | Orquestador, agentes, skills, capa de memoria y canon. Todo lo especificado en `docs/architecture.md` |
| `frontend/` | React + Three.js | Interfaz de lectura y visualización del estado del mundo, del grafo canónico y de la curva de tensión |

Dos consecuencias que conviene tener claras desde ya:

- **El frontend no participa en el ciclo de generación.** Observa y muestra; no aprueba, no corrige, no desbloquea. Cualquier interacción que condicione al ciclo viola la restricción de autonomía (§5.3.1).
- **El backend es el único dueño del canon.** El frontend lee proyecciones del estado; no escribe en él (§5.3.3).

---

## 4. Los cuatro documentos

Están pensados para leerse en este orden. Cada uno depende del anterior.

### [`docs/definitions.md`](docs/definitions.md) · Ontología

Glosario con identificadores estables agrupados en diez capas: metamodelo (`MET`), estructura narrativa (`EST`), personajes (`PER`), mundo (`MUN`), subdominio deportivo (`DEP`), poética (`POE`), canon (`CAN`), contexto (`CTX`), calidad (`CAL`) y proceso (`PRO`). Incluye invariantes verificables.

**Consúltalo cuando**: necesites saber qué significa un término o qué ID usar.

### [`docs/domain-knowledge.md`](docs/domain-knowledge.md) · Modelos

16 diagramas Mermaid: mapa de capas, árbol estructural, modelo entidad-relación del núcleo, anatomía de escena, árboles por capa, ciclo setup-payoff, ciclo de vida del capítulo y mapa de modos de fallo.

**Consúltalo cuando**: necesites entender cómo se relacionan las entidades o qué causa un tipo de defecto.

### [`docs/architecture.md`](docs/architecture.md) · Arquitectura

Capa de memoria en cinco almacenes, ingeniería de contexto con presupuestos en tokens, catálogo de 33 skills, catálogo de 13 agentes, flujos del sistema y política de arbitraje.

**Consúltalo cuando**: vayas a implementar cualquier componente o necesites saber qué agente hace qué.

### [`docs/validations.md`](docs/validations.md) · Validaciones

Catálogo completo de comprobaciones con ID, tipo, regla, severidad, puerta y acción al fallar. Nueve familias más la meta-validación que vigila a los validadores.

**Consúltalo cuando**: implementes una comprobación o necesites saber qué significa "correcto" para un artefacto.

---

## 5. Reglas de trabajo en el repositorio

### 5.1 Identificadores

- Los IDs (`EST-07`, `CTX-13`, `VAL-DEP-05`) son **estables**. Nunca se reasignan ni se reciclan.
- Al retirar un término, se marca como obsoleto con su sustituto. No se borra.
- Al añadir uno, se usa el siguiente número libre de su familia.
- Las referencias cruzadas entre documentos van siempre por ID, nunca por nombre.

### 5.2 Coherencia entre documentos

Un cambio conceptual toca los cuatro documentos o ninguno:

| Si cambias... | Actualiza también |
|---|---|
| Un término en `definitions.md` | Los diagramas que lo usan y las tablas que lo referencian |
| Un agente o skill en `architecture.md` | La matriz agente × skill y los flujos |
| Una validación en `validations.md` | La matriz puerta × familia y el conjunto dorado |
| Un presupuesto de tokens | La tabla por agente y el total de ocupación |

### 5.3 Restricciones que no se negocian

1. **Nada de intervención humana.** Si al diseñar aparece un paso de aprobación, revisión o confirmación manual, es un error de diseño. Sustitúyelo por regla, umbral o agente.
2. **100.000 tokens es el techo.** Entrada ≤70.000, entrada más salida ≤85.000. Lo que no quepa se resuelve con jerarquía de resúmenes y recuperación selectiva, nunca con truncamiento.
3. **El canon es la fuente de verdad.** Ninguna propuesta puede hacer que la verdad viva solo en la prosa.
4. **Determinista antes que modelo.** Si algo se puede comprobar con código, no se le pregunta a un modelo.
5. **Evidencia obligatoria.** Cualquier veredicto sin cita localizable se descarta.
6. **Fallo cerrado.** Una validación que no puede ejecutarse cuenta como fallida.

### 5.4 Convenciones de escritura

- **Idioma: español.** Los identificadores técnicos, nombres de skills y claves de datos van en inglés (`scene.write`, `canon.query`).
- Prosa directa, sin relleno. Frases cortas. Se evita el énfasis decorativo y las fórmulas de transición vacías.
- Los diagramas son Mermaid dentro de bloques de código. Las etiquetas de nodo van siempre entre comillas, y se evitan paréntesis y caracteres especiales dentro de ellas.
- Las tablas se prefieren a las listas cuando hay más de dos atributos por elemento.
- Cada documento abre con un bloque de referencias cruzadas a los otros tres.

### 5.5 Alcance: solo esta rama

La única fuente de información válida es el estado actual de la rama de trabajo (`v2`): `AGENTS.md`, `CLAUDE.md` y los cuatro documentos de `docs/`.

- **No se consulta el historial de git**, ni ramas anteriores, ni commits previos, ni ficheros borrados, ni la carpeta `ui/` retirada.
- **No se reintroduce** nada que existiera en una versión anterior por el hecho de haber existido. Si algo hace falta, se justifica desde cero contra los documentos de hoy.
- Las especificaciones describen **solo el sistema de hoy**. No llevan notas de lo que se quitó, ni comparativas con versiones pasadas, ni arqueología.
- Si un documento cita algo que ya no está en la rama, es una inconsistencia: se señala y se corrige, no se rescata el original.

**Por qué**: el proyecto arrancó de cero en esta rama. Arrastrar decisiones de versiones anteriores reintroduce restricciones que ya no aplican y hace que los cuatro documentos dejen de describir un sistema único y coherente.

---

## 6. Los 13 agentes especificados

Referencia rápida. El detalle está en `docs/architecture.md` §6. **Ninguno está implementado.**

| # | Agente | Misión |
|---|---|---|
| 0 | Orquestador | Dirige el flujo y cuenta reintentos. Código, no modelo |
| 1 | Arquitecto narrativo | Arcos, doble arco, curva de tensión, escaleta |
| 2 | Planificador de capítulo | Especificaciones de escena |
| 3 | Documentalista | Ensambla el paquete de contexto. Código |
| 4 | Escritor de escena | Produce la prosa |
| 5 | Especialista deportivo | Resuelve y narra encuentros |
| 6 | Continuista | Verificación de continuidad |
| 7 | Jurado (×3) | Evalúa dimensiones subjetivas |
| 8 | Reparador | Corrección dirigida |
| 9 | Estilista | Pase de voz, poda y proscripción |
| 10 | Archivero | Extrae el delta canónico y resume |
| 11 | Árbitro | Resuelve conflictos por precedencia |
| 12 | Supervisor | Vigila deuda, tensión y deriva; replanifica |

Tres son los que suelen faltar en implementaciones ingenuas: **Archivero** (sin él el canon se queda atrás respecto al texto), **Árbitro** (sin él un conflicto detiene el sistema, porque no hay a quién preguntar) y **Supervisor** (sin él la novela pierde forma en el segundo acto sin que nada lo señale).

---

## 7. Orden de implementación previsto

1. Canon estructurado + registro de eventos
2. Especificación de escena y escaleta
3. Documentalista con presupuesto fijo
4. Escritor de escena + validaciones deterministas
5. Archivero y ciclo de congelación
6. Árbitro y política de precedencia ← **desde aquí el sistema es autónomo**
7. Resúmenes jerárquicos
8. Recuperación híbrida
9. Jurado, conjunto dorado y Estilista
10. Supervisor, replanificación y métricas

Los pasos 1 a 6 producen una novela coherente sin intervención. Del 7 en adelante se gana escala y calidad, no viabilidad.

---

## 8. Antes de proponer un cambio

Cinco preguntas. Si alguna falla, el cambio no está listo:

1. ¿Usa el vocabulario de `definitions.md` con sus IDs?
2. ¿Respeta las seis restricciones de §5.3?
3. ¿Cabe en 100.000 tokens con el presupuesto de su agente?
4. ¿Tiene una validación en `validations.md` que compruebe que funciona?
5. ¿Se apoya solo en el estado actual de esta rama, sin recuperar nada de versiones anteriores (§5.5)?
