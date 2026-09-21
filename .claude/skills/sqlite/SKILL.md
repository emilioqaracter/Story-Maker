---
name: sqlite
description: "Trabajar con la persistencia de Story-Maker en SQLite: esquema de los cinco almacenes de la capa de memoria, registro de eventos append-only, grafo de entidades, índice de prosa con FTS5, resúmenes jerárquicos, migraciones y consultas. Úsala al crear o modificar cualquier tabla, índice, vista o consulta del backend."
---

# Persistencia · SQLite

Cómo se guarda el estado en este proyecto. El esquema lógico está en `docs/architecture.md` §3; el motivo de la elección, en `AGENTS.md` §3.2.

Antes de crear cualquier fichero, pasa por el proceso C de `AGENTS.md` §6.4.

El esquema vive en `backend/canon/`, que es la funcionalidad dueña de los cinco almacenes (`architecture.md` §2.3). Ninguna otra funcionalidad abre la base directamente: consulta a través de `canon/`.

## 1. Un fichero por novela, en local

Sin servidor. La tirada entera cabe en un fichero, y copiarlo es copiar el estado completo: eso es lo que hace reproducible una tirada, y lo que sirve al conjunto dorado (CAL-10) y a los evals (VER-10).

No hay concurrencia entre tiradas. Dentro de una, **el Archivero es el único que escribe canon**, y solo al congelar un capítulo. Todo lo demás abre en solo lectura (VER-11).

## 2. Cinco almacenes, una base

Separación lógica, no física: cinco conjuntos de tablas conviviendo. Unificarlos en un único índice vectorial es el error estructural más frecuente en este tipo de sistema, y tenerlos en cinco bases sería la sobrecorrección.

| Almacén | Implementación |
|---|---|
| Canon estructurado | Tablas relacionadas con columna de versión |
| Registro de eventos | Tabla append-only, más vistas materializadas por proyección |
| Grafo de entidades | Tabla de aristas con vigencia desde y hasta, recorrida con CTE recursivo |
| Índice de prosa | FTS5 para el léxico, que ya trae BM25 |
| Resúmenes jerárquicos | Tabla con nivel y referencia al padre |

Esos cinco son la memoria de **largo plazo**: lo que es verdad y sobrevive a la congelación.

## 2.1 Las tablas efímeras

Aparte viven las de **memoria de trabajo** (PRO-13, `architecture.md` §3.2): lo que el sistema sostiene mientras produce un capítulo y todavía no es verdad.

| Tabla | Guarda | Se vacía |
|---|---|---|
| `run_state` | Capítulo, escena y paso en curso. Es el punto de reanudación, PRO-14 | Al terminar la novela |
| `draft` | Prosa sin congelar | Al congelar: pasa al índice de prosa |
| `defect` | Defectos abiertos con su evidencia | Al congelar |
| `verdict` | Puntuaciones del jurado y su dispersión | Al congelar |
| `admission` | Llamadas en vuelo y cola de CTX-20 | Al terminar cada llamada |

Tres cosas que importan al escribir el esquema:

- **Márcalas como efímeras en el propio esquema**, con prefijo o con un `schema` aparte. Que se distingan de un vistazo es lo que impide que una consulta de canon lea un borrador por error.
- **La purga al congelar es una transacción**, junto con la escritura del delta. A medias deja huérfanos, y el invariante PRO-I1 dice que tras congelar no queda ninguna fila del capítulo.
- **No las archives en tablas históricas.** Esa traza es de Langfuse (VER-09). Aquí se guarda lo que es verdad, no lo que pasó.

## 3. El registro de eventos manda

Es la regla de consistencia del sistema (`architecture.md` §3):

- El registro de eventos es **append-only**. No se actualiza ni se borra una fila; se añade el evento que corrige.
- Canon estructurado y grafo son **proyecciones reconstruibles**. Si divergen del registro, se regeneran; no se parchean.
- El índice de prosa **se reindexa al congelar** un capítulo.

Corolario práctico: cualquier `UPDATE` o `DELETE` sobre la tabla de eventos es un bug, no una optimización. Impídelo con un trigger, no con una convención.

## 4. Consultas que el esquema debe resolver bien

Son las que el sistema hace de verdad, así que son las que guían el diseño de índices:

| Consulta | Qué exige |
|---|---|
| «Qué sabía el protagonista en la jornada 14» | Proyección del registro filtrada por personaje e instante |
| «Dame la ficha del entrenador» | Lectura directa del canon estructurado |
| «Quién tiene conflicto abierto con quién» | Aristas vigentes en t, con CTE recursivo |
| «Cómo describí el estadio la primera vez» | FTS5 con filtro previo por metadatos |
| «Resume los actos I y II» | Recorrido por nivel en los resúmenes |

**El troceado del índice de prosa es por escena, no por bloque de N tokens.** Cada trozo lleva capítulo, POV, lugar, instante de mundo y personajes presentes, de modo que la recuperación filtre antes de puntuar. Es lo que hace barata la consulta y precisa la respuesta.

## 5. La decisión abierta que no debes cerrar por tu cuenta

SQLite no hace búsqueda vectorial de serie. FTS5 cubre el lado léxico con BM25, pero la recuperación híbrida (CTX-08) necesita además similitud semántica.

Hay tres salidas —extensión vectorial para SQLite, embeddings en tabla con el cálculo en Python, o quedarse en FTS5 más filtro por metadatos— y **ninguna está elegida**. Está registrada como decisión abierta nº 7 en `architecture.md` §13.

Si tu trabajo la necesita, **para y ejecuta el proceso B de `AGENTS.md` §6.3**. Añadir una dependencia vectorial es cerrar la decisión de facto.

## 6. Verificación

- Las migraciones son código y pasan la puerta de CI como el resto (VER-15).
- Los invariantes del esquema se prueban con `hypothesis` (VER-06): «fusionar dos deltas es asociativo», «toda arista tiene vigencia coherente», «reconstruir la proyección desde cero da el mismo resultado que la incremental», «congelar no deja ninguna fila de memoria de trabajo» (PRO-I1).
- Ninguna consulta se construye concatenando cadenas que vengan de un modelo. Parámetros siempre (VER-02).
