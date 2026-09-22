---
name: sqlite
description: "Trabajar con la persistencia de Story-Maker en SQLite: esquema de los cinco almacenes de la capa de memoria, registro de eventos append-only, grafo de entidades, índice de prosa con FTS5, resúmenes jerárquicos, migraciones y consultas. Úsala al crear o modificar cualquier tabla, índice, vista o consulta del backend."
---

# Persistencia · SQLite

Cómo se guarda el estado en este proyecto. El esquema lógico está en `docs/architecture.md` §3; el motivo de la elección, en `AGENTS.md` §3.2.

Antes de crear cualquier fichero, pasa por el proceso C de `AGENTS.md` §6.4.

El esquema vive en `backend/canon/`, que es la funcionalidad dueña de los cinco almacenes (`architecture.md` §2.3). Ninguna otra funcionalidad abre la base directamente: consulta a través de las skills `canon.*` de `canon/`, que es la excepción de lectura de `architecture.md` §2.3.

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
| Índice de prosa | Dos niveles, escena y fragmento; FTS5 para el léxico, que ya trae BM25, más tabla de vectores con modelo y dimensión |
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

**El índice de prosa tiene dos niveles** (`architecture.md` §3.1). Una fila por escena, con sus metadatos y el vector de su resumen, que es lo que decide qué escenas miran; y filas de fragmento dentro de cada escena, de hasta 450 tokens por párrafos completos con un párrafo de solape, que son lo que se inyecta.

**Un fragmento nunca cruza la frontera de su escena** y hereda sus metadatos por clave ajena: capítulo, POV, lugar, instante de mundo y personajes presentes. Así el filtro se aplica antes de puntuar, que es lo que hace barata la consulta y precisa la respuesta.

**Solo entra prosa congelada.** Un borrador no se indexa ni marcado como provisional: la escena siguiente podría recuperar texto que aún puede desaparecer, que es el camino corto al envenenamiento de contexto (CTX-13).

## 5. Los vectores van en una tabla, no en una extensión

SQLite no hace búsqueda vectorial de serie, y aquí **no se añade ninguna extensión que se la dé** (`architecture.md` §3.1). El embedding de cada trozo se guarda como blob en una tabla, junto con el identificador del modelo que lo produjo y su dimensión, y la similitud se calcula en Python sobre el conjunto que ya filtraron los metadatos.

Funciona porque el conjunto es pequeño: una obra troceada por escena da del orden de 200 a 400 trozos, y el filtro previo deja menos. El recorrido exhaustivo es exacto y un índice aproximado solo añadiría error.

Tres consecuencias al escribir el esquema:

- **El fichero sigue siendo un SQLite corriente.** Nada de cargar extensiones nativas: es lo que mantiene cierta la promesa de que copiar el fichero es copiar el estado completo, vectores incluidos.
- **Modelo y dimensión son columnas, no supuestos.** Vectores de modelos distintos no se comparan; encontrarlos mezclados dispara reindexación.
- **La escritura del índice va dentro de la transacción de congelación**, con los vectores ya calculados antes de abrirla. Congelar la prosa y dejar el índice a medias rompe la recuperación en silencio.

## 6. Verificación

- Las migraciones son código y pasan la puerta de CI como el resto (VER-15).
- El orden de escritura al congelar lo fija `architecture.md` §3.3: fragmentar, resumir y embeber **fuera** de la transacción; eventos, proyecciones, índice, resúmenes y purga **dentro**. Una transacción abierta esperando a un proveedor externo bloquea el fichero y deja el estado a medias si el proceso cae.
- Los invariantes del esquema se prueban con `hypothesis` (VER-06): «fusionar dos deltas es asociativo», «toda arista tiene vigencia coherente», «reconstruir la proyección desde cero da el mismo resultado que la incremental», «congelar no deja ninguna fila de memoria de trabajo» (PRO-I1).
- Ninguna consulta se construye concatenando cadenas que vengan de un modelo. Parámetros siempre (VER-02).
