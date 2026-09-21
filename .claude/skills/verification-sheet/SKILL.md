---
name: verification-sheet
description: "Producir docs/verification.md a partir de un context seed: elegir con qué método se verifica cada artefacto de un sistema, clasificarlo en TAIDU, fijar herramienta, umbral y límite, y declarar lo que queda sin verificar. Úsala para crear o regenerar verification.md, para decidir qué método cubre un artefacto nuevo, o cuando haya que justificar por qué algo no está verificado."
---

# Hoja de verificación

Convierte un **context seed** en el `verification.md` de ese sistema: el mapa de qué técnica se aplica a qué artefacto, con qué garantía y a qué coste.

El catálogo de 18 métodos y el esquema TAIDU son **fijos**: están en §3 y no se inventan. Lo que cambia en cada sistema es qué verifica cada método *ahí*, con qué herramienta, con qué umbral, y cuáles sobran.

Los enlaces canónicos de cada método están en [`reference.md`](reference.md). Cárgalo solo al escribir las citas.

---

## 1. Qué es el context seed

El conjunto de documentos que describen el sistema a verificar. Como mínimo hace falta sacar de ellos cuatro cosas; si alguna falta, **pídela antes de empezar**, porque sin ella el resultado es genérico y por tanto inútil:

| Qué necesitas | Para qué |
|---|---|
| **Artefactos verificables** | Son las filas de la matriz de §5. Código, contratos, salidas de modelo, flujos, datos |
| **Restricciones duras** | Lo que el sistema promete y hay que comprobar que cumple |
| **Invariantes ya enunciados** | Se traducen a propiedades casi sin trabajo. Ver §4, regla 5 |
| **Stack** | Determina la herramienta concreta de cada método |

En Story-Maker el seed son `AGENTS.md`, `docs/definitions.md` y `docs/architecture.md`.

---

## 2. Procedimiento

1. **Leer el seed entero** y listar los artefactos verificables. Esa lista es el eje de todo lo demás: si un artefacto no aparece aquí, no acabará cubierto.
2. **Separar los dos ejes.** Verificación de **producto** (¿el código hace lo que dice?) y de **proceso** (¿el agente se comporta de forma fiable?). Son independientes: un backend sin bugs puede orquestar agentes que escriben basura coherente. Cubrir solo uno es el modo de fallo característico de los sistemas agénticos.
3. **Recorrer los 18 métodos de §3, uno por uno.** Para cada uno: ¿qué verifica **en este sistema**? Si la respuesta es «nada», se excluye **y se escribe por qué**. Un método ausente sin explicación se lee como un olvido.
4. **Asignar la clase TAIDU** con las reglas de §4.
5. **Fijar herramienta, límite y puerta** de cada método. El límite es obligatorio: un método sin límite escrito produce confianza falsa.
6. **Construir la matriz método × artefacto.** Toda fila necesita al menos un método.
7. **Lo que no cubre ninguno va al registro de riesgo aceptado**, con su motivo y con la señal que se vigilará en su lugar. Nunca en blanco.
8. **Dibujar la cascada**: qué corre en cada push, qué de noche, qué por campaña, y dónde se cruzan los dos ejes.

---

## 3. El catálogo

Fijo. No se añaden métodos por gusto ni se renombran: son los nombres reconocidos en la literatura, y cambiarlos rompe la trazabilidad con las referencias de [`reference.md`](reference.md).

### 3.1 Verificación de producto · ¿el código es correcto?

| # | Método | Definición |
|---|---|---|
| 1 | **Type checking** | Comprobación automática de que los valores se usan de forma consistente con lo que las operaciones esperan |
| 2 | **Static analysis / SAST** | Escaneo del código sin ejecutarlo, contra patrones conocidos como malos |
| 3 | **Symbolic execution** | Ejecución con entradas simbólicas para derivar, vía solver SMT, las condiciones exactas de fallo |
| 4 | **Formal verification / theorem proving** | Demostración matemática de que el código satisface una especificación para todas las entradas |
| 5 | **Unit / integration testing** | Comprobación del comportamiento contra entradas de ejemplo concretas y salidas esperadas |
| 6 | **Property-based testing** | Enunciar una propiedad general y generar muchas entradas buscando una violación |
| 7 | **Mutation testing** | Introducir bugs pequeños a propósito para comprobar si la batería de tests los detecta |
| 8 | **Contract testing** | Verificar que la interfaz entre dos servicios se mantiene consistente, con independencia de las tripas |

### 3.2 Verificación de proceso · ¿el agente se comporta de forma fiable?

| # | Método | Definición |
|---|---|---|
| 9 | **Runtime observability / tracing** | Instrumentar al agente para que su trayectoria real sea visible y consultable después |
| 10 | **Evals** | Pruebas estructuradas del comportamiento contra un conjunto de datos y un método de puntuación |
| 11 | **Sandboxed execution** | Ejecutar en un entorno aislado, de modo que una acción mala falle sin consecuencias |
| 12 | **Guardrails** | Políticas o filtros que acotan qué acciones y salidas puede producir un agente, **antes** de actuar |
| 13 | **Human-in-the-loop review** | Una persona aprueba, rechaza o edita las acciones de alto impacto |
| 14 | **Multi-agent verification** | Patrones de crítico, debate, autoconsistencia, reflexión o ensemble que revisan la salida |
| 15 | **CI/CD integration** | Enrutar los cambios generados por agentes por el mismo pipeline que el código humano |
| 16 | **Progressive rollout** | Desplegar tras un flag, a un porcentaje pequeño, vigilado antes de liberarlo del todo |
| 17 | **Red-teaming / adversarial testing** | Sondear fallos a propósito bajo un modelo de amenaza adversario |
| 18 | **Model checking** | Explorar de forma exhaustiva los estados y transiciones alcanzables para verificar invariantes |

### 3.3 TAIDU · esquema de clasificación

Todo elemento verificable recibe **una** clase. La clase dice **cómo** se obtiene la confianza, no **cuánta** hay.

| Clase | Nombre | Se verifica | Garantía |
|---|---|---|---|
| **T** | Test | Ejecutando el sistema contra entradas concretas | Solo sobre lo ejecutado |
| **A** | Analysis | Razonamiento estático: tipos, SAST, ejecución simbólica, prueba formal | Sobre todas las entradas del dominio analizado |
| **I** | Inspection | Alguien lee y juzga | Depende del juez; exige evidencia citada |
| **D** | Demonstration | Observando operación correcta en un escenario realista | Sobre el escenario observado |
| **U** | Unverifiable | Ningún método aplica, o no compensa su coste | Ninguna. Es riesgo aceptado |

---

## 4. Reglas de asignación

1. **A antes que T antes que D antes que I.** Si algo se puede decidir con tipos o con un solver, no se le pregunta a un modelo.
2. **I solo para lo irreductiblemente subjetivo.** Casi nada lo es. Todo lo demás que caiga en I es un fallo de diseño: significa que no se ha sabido enunciar la regla.
3. **U se declara, no se hereda.** Nada entra en U por olvido: entra por decisión escrita, con motivo y con la señal sustitutiva.
4. **Fallo cerrado.** Un método que no puede ejecutarse cuenta como fallado, nunca como pasado.
5. **Los invariantes del seed se traducen a property-based testing casi sin trabajo.** Si el seed ya los escribió como propiedades universales, convertirlos es mecánico, y es la mejor relación coste-cobertura que vas a encontrar. Búscalos antes de inventar propiedades nuevas.
6. **Cada método activo lleva su límite escrito.** Qué *no* garantiza. Sin esa línea, el lector supone cobertura que no existe. Un método excluido está exento: no cubre nada, así que no hay cobertura que acotar.

### Sobre el método 13

**No se excluye por norma.** Se excluye si el seed declara autonomía sin intervención humana, y entonces la exclusión se documenta diciendo qué ocupa su lugar: qué hace el sistema en cada punto donde habría decidido una persona. Si esos sustitutos ya están tabulados en otro documento del seed, se enlazan; no se copian. Si el seed no dice nada de autonomía, el método 13 entra como cualquier otro.

La exclusión es consecuencia del seed, nunca del catálogo.

---

## 5. Estructura de salida

`verification.md` sale con estas secciones, en este orden:

| § | Contenido |
|---|---|
| 1 | Los dos ejes, producto y proceso, con qué objeto cubre cada uno y cuándo corre |
| 2 | TAIDU y sus reglas de asignación |
| 3 | Mapa de métodos: tabla de `VER-NN`, eje, clase y dónde corre |
| 4 | Verificación de producto, un apartado por método |
| 5 | Verificación de proceso, un apartado por método |
| 6 | Cascada de verificación, en diagrama |
| 7 | Matriz método × artefacto |
| 8 | Cómo se elige el método |
| 9 | Registro de riesgo aceptado |
| 10 | Referencias canónicas, una por método, desde [`reference.md`](reference.md) |

Cada apartado de §4 y §5 lleva la misma tabla: **qué verifica aquí**, **clase**, **herramienta**, **límite** y, si lo tiene, **umbral**. Después, un párrafo corto con el porqué de la decisión, no una paráfrasis de la tabla.

Los IDs van `VER-01` a `VER-18` siguiendo el orden de §3. Son estables: no se reciclan ni se renumeran.

---

## 6. Lo que invalida el resultado

Si al terminar se cumple cualquiera de estas, el documento no está listo:

- Una fila de la matriz de §7 sin ningún método, y sin entrada en §9.
- Un método clasificado como **I** que se podría haber enunciado como regla comprobable.
- Un umbral numérico sin origen. Si es nuevo, se marca como propuesta y se explica de dónde sale.
- Un método sin línea de límite.
- El método 13 excluido sin decir qué ocupa su lugar, o incluido cuando el seed prohíbe la intervención humana. Basta con enunciar los sustitutos y enlazar dónde viven: si ya están tabulados en otro documento del seed, **no se copian aquí**.
- Un apartado que repite lo que el seed ya dice en vez de decidir algo nuevo. Este documento elige métodos; no reexplica la arquitectura.

---

## Procedencia

El catálogo de 18 métodos, sus definiciones y el esquema TAIDU vienen de la hoja de referencia «Verification Methodologies — Reference Sheet», un artefacto público ajeno a este repositorio. Se ha tomado como **datos**: un catálogo de metodologías reconocidas con sus referencias académicas y estándares. Todo lo que este documento dice sobre cómo aplicarlo —el procedimiento, las reglas de asignación y los criterios de invalidación— es de este repositorio, no de la fuente.
