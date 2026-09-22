# Plan de implementación · backend v1

> Compañero de [`specs/srs-backend-v1.md`](../specs/srs-backend-v1.md), que dice **qué** hay que construir. Este documento dice **en qué orden y con qué ficheros**.
> No es un SRS y no añade requisitos: todo lo que aparece aquí tiene su `RF`, `RD`, `RI` o `RNF` en la spec. Si algo no lo tiene, es un error de este documento.

---

## 1. Antes de escribir una línea

### 1.1 Lo que ya está decidido y no se vuelve a discutir

Si al implementar te parece que alguna de estas está mal, eso dispara el proceso B de [`AGENTS.md`](../AGENTS.md) §6.3, no un parche en el código.

| | Decisión | Dónde está |
|---|---|---|
| Modelo | Claude Haiku 4.5 para los once agentes | D-23 |
| Embeddings | Modelo multilingüe local con `fastembed`, dentro de la imagen | D-22 |
| Contador | `tiktoken` × factor, calibrado al arrancar. **Nunca crudo** | D-14, D-28 |
| Vectores | En tabla, similitud en Python, sin extensión nativa | D-12 |
| Persistencia | Un fichero SQLite por novela | RI-14 |
| Rutas | Dentro de cada funcionalidad; la aplicación se compone en `orchestration/` | D-01 |
| Contexto | Empuje para todos; tirón además para cinco agentes | D-19 |
| Tiempo de mundo | ISO 8601 más `world_seq` de desempate | D-07 |
| Retcon | No existe en v1: el canon congelado siempre gana | D-05 |

### 1.2 La regla de importación, activa desde el primer commit

Tres pisos, y se comprueba con `import-linter` en CI (RNF-15) **desde el tramo 0**, no al final:

```
orchestration/          ← conoce a todas; nadie lo conoce a él
    ↓
planning/  context/  generation/  verification/
    ↓
canon/                  ← todas leen de él; él no importa de ninguna
commons/                ← cualquiera puede importarlo
```

Dejarlo para el final significa descubrir en el tramo 8 que media docena de módulos cruzan la frontera, y reorganizarlos cuando ya tienen tests encima.

### 1.3 Diez trampas que van a morder

Están aquí porque las diez producen código que **funciona en la demo y falla en el capítulo 20**.

1. **`tiktoken` crudo.** Infracuenta en español. Todo lo que devuelve va multiplicado por el factor y redondeado hacia arriba. Un solo sitio que lo llame directo rompe el techo (RI-20).
2. **Algo voluble delante del prefijo cacheable.** Una marca de tiempo, un identificador de tirada, un contador de intento. El caché casa por prefijo: un byte distinto y se pierde la llamada entera, sin error (RF-103).
3. **La conexión de escritura fuera de `canon/`.** Ponla en `canon/db/` desde el principio; si vive en `commons/` alguien la importará (RD-09).
4. **Proyecciones que dependen del orden de inserción.** Ordena siempre por `(world_time, world_seq, id)`. La propiedad que lo detecta va en el tramo 1, no después (RD-03, RF-04).
5. **Fragmentos que cruzan la frontera de su escena.** Rompe el filtrado por metadatos, que es lo que hace barata la recuperación (RD-16, RF-70).
6. **Truncar.** Ni un fragmento, ni un paquete, ni un resultado de herramienta. Se sustituye por resumen o se niega (RF-84, RF-94).
7. **Escenas en paralelo.** El bloque 6 del paquete del Escritor es la prosa literal de la anterior. Van en serie, siempre (RF-45).
8. **Empezar el capítulo N+1 con el N sin congelar.** No existe para el sistema (RF-107).
9. **Cálculo de embeddings dentro de la transacción.** Son cientos de vectores; bloquean el fichero sin motivo (RNF-21, RF-68).
10. **La memoria de trabajo en un paquete.** Un borrador rechazado que llega al Escritor es el sistema aprendiendo de su propio error (RF-37).

---

## 2. Los ocho tramos

Cada tramo abre cuando el anterior pasa su puerta. El detalle de qué entrega y con qué se comprueba está en el SRS §11; aquí va el contenido fichero a fichero.

### T0 · `commons/`

Todo lo demás importa de aquí, así que va primero aunque no sea una funcionalidad.

```
commons/
├── provider/
│   ├── port.py           · protocolo: complete_once, complete_with_tools, embed
│   ├── claude.py         · implementación Haiku 4.5; traduce el esquema de salida
│   ├── embeddings.py     · fastembed; carga y verificación de dimensión al arrancar
│   └── errors.py         · tipos de fallo del proveedor
├── tokens/
│   ├── counter.py        · tiktoken × factor, redondeo hacia arriba
│   ├── factors.py        · un factor por modelo; sin factor, no se admite
│   └── calibration.py    · llamada de calibración al arrancar
└── types/                · artefactos que cruzan dos o más funcionalidades
    ├── outline.py  scene_spec.py  context_package.py
    ├── defect.py   canon_delta.py  arbitration.py
    └── prose.py
```

| Requisitos | RI-11 a RI-13, RI-20 a RI-22, RI-24, RNF-16, RNF-19 |
|---|---|
| **Puerta** | `mypy --strict` limpio; el contador contrastado contra un `usage` de doble |

**Lo que más importa de este tramo:** `port.py` tiene **dos** modos de `complete`, y quién usa cuál no lo decide el agente sino su ficha en `architecture.md` §6.3. Si el puerto expone uno solo, los cinco agentes con herramientas no tienen dónde vivir.

### T1 · `canon/` · esquema y lectura

```
canon/
├── db/
│   ├── connection.py     · dos fábricas: lectura y escritura. La de escritura NO sale de aquí
│   ├── schema.sql        · las tablas de los cinco almacenes
│   ├── triggers.sql      · abortan UPDATE y DELETE sobre event
│   └── migrations/       · versión de esquema; hacia delante en escritura
├── events/               · inserción y lectura del registro
├── projections/          · entity, alias, attribute, relation, knowledge, competence, document_version
├── graph/                · recorrido recursivo sobre aristas vigentes
└── skills/
    ├── query.py  state_at.py  knowledge_of.py  related.py
```

| Requisitos | RD-01 a RD-17, RF-01 a RF-11, RF-67 |
|---|---|
| **Puerta** | Independencia del orden de inserción; reconstruibilidad desde cero; vigencia correcta en cualquier instante |

**Escribe estas tres propiedades antes que las funciones**, porque las tres son de las que se comprueban generando casos, no ejemplos: proyectar los mismos eventos en distinto orden da el mismo estado; regenerar el canon desde cero es igual a mantenerlo incremental; una consulta en `t` no devuelve nada cuya vigencia haya terminado antes de `t`.

### T2 · `planning/`

```
planning/
├── outline/
│   ├── plan.py           · outline.plan, agente de modelo
│   └── check.py          · outline.check, DETERMINISTA
├── scene_spec/           · conversión de tramo a especificaciones
├── ledger/               · registro de setups y su máquina de estados
├── act_gate/             · puerta de cierre de acto
└── routes.py             · GET /novels/{id}/debt
```

| Requisitos | RF-25 a RF-31, RF-105, RF-106 |
|---|---|
| **Puerta** | `outline.check` rechaza una escaleta con un arco sin resolución y acepta una válida |

**`check.py` no llama a ningún modelo.** Es un verificador estructural: cobertura de arcos, doble arco resuelto en escenas distintas, curva de tensión monótona por acto, todo setup con payoff planificado, reparto de palabras. Si te ves pidiéndole a un modelo que valide la escaleta, has cruzado la restricción de «determinista antes que modelo».

### T3 · `context/`

El tramo más grande, y donde vive el RAG híbrido.

```
context/
├── query/                · filtros, términos léxicos desde alias, texto semántico, exclusiones
├── retrieval/
│   ├── lexical.py        · FTS5 con BM25
│   ├── semantic.py       · coseno sobre vectores, en Python
│   ├── fusion.py         · fusión recíproca de rangos, constante 60
│   └── quotas.py         · lugar, voz, promesa, espejo, libre
├── packing/
│   ├── assemble.py       · ensamblaje por receta
│   ├── compact.py        · prioridad inversa; nunca trunca
│   └── recipes/          · una por agente destino
└── audit/                · context.audit
```

| Requisitos | RF-32 a RF-39, RF-72 a RF-89, RF-103, RNF-20, RNF-23 |
|---|---|
| **Puerta** | La fusión es determinista sobre el mismo canon; ningún paquete supera el presupuesto de su agente destino |

**Cero llamadas de modelo en todo el tramo**, salvo el vector de la consulta, que además ahora es local. Si aparece una, algo está mal planteado: los sinónimos salen de la tabla de alias y la consulta semántica es la propia especificación de escena.

### T4 · `generation/`

```
generation/
├── writer/               · scene.write
└── sports/
    ├── simulate.py       · motor de reglas, DETERMINISTA dada una semilla
    └── narrate.py        · dramatiza la cronología ya resuelta
```

| Requisitos | RF-40 a RF-45 |
|---|---|
| **Puerta** | `match.simulate` es determinista dada una semilla y no alinea a nadie indisponible |

**`simulate.py` corre antes que `narrate.py`, siempre.** El marcador, la cronología de hitos y los cambios de estado físico los decide el motor de reglas; el modelo solo los dramatiza. Invertirlo reintroduce toda la familia de defectos de verosimilitud deportiva que este diseño elimina de raíz.

### T5 · `verification/`

```
verification/
├── checks/               · timeline, ledger, availability, format, repetition, lexicon, knowledge
├── continuity/           · continuity.review, agente de modelo con herramientas
└── repair/               · revise.targeted; revalida desde la primera puerta
```

| Requisitos | RF-46 a RF-54 |
|---|---|
| **Puerta** | Cobertura de mutación ≥ 90 % en los siete verificadores deterministas |

**El 90 % de mutación se acota a `checks/` y no al resto**, porque son la red de seguridad del sistema entero: un verificador cuyos tests no detectan su ruptura es peor que no tener verificador, porque produce confianza falsa.

### T6 · `canon/` · escritura

```
canon/
├── prose_index/
│   ├── chunk.py          · por párrafos, ≤450 tokens, un párrafo de solape
│   ├── embed.py          · llama al modelo local de commons/
│   └── index.py          · dos niveles: escena y fragmento; FTS5 y vectores
├── summaries/            · escena y capítulo
├── archivist/            · delta.extract
└── freeze/               · la transacción
```

| Requisitos | RF-12, RF-55 a RF-58, RF-68 a RF-71, RF-90, RNF-21 |
|---|---|
| **Puerta** | Congelar no deja ninguna fila de memoria de trabajo; un fallo de embeddings no escribe nada |

**El orden de `freeze/` es la mitad del tramo.** Fuera de la transacción: cortar, resumir, vectorizar. Dentro y todo junto o nada: eventos, proyecciones, índice, resúmenes, purga. Escribirlo al revés deja el fichero bloqueado mientras se calculan cientos de vectores.

### T7 · `canon/` · arbitraje

```
canon/
└── arbiter/
    ├── precedence.py     · la política, total y sin ciclos
    └── entries.py        · las dos puertas: Orquestador y Documentalista
```

| Requisitos | RF-59 a RF-63 |
|---|---|
| **Puerta** | La precedencia es total y sin ciclos; fusionar dos deltas es asociativo |

**Desde aquí el sistema es autónomo.** Antes de este tramo, cualquier contradicción lo detiene porque no hay quién la resuelva.

### T8 · `orchestration/`

```
orchestration/
├── loop.py               · bucles de capítulo y de escena
├── checkpoint.py         · punto de reanudación, al cerrar cada escena
├── admission.py          · semáforo de entrada, FIFO estricta, cupos de tirón
├── retries.py            · presupuesto de reintentos y cuarentena por nivel
├── dispatch.py           · frontera de confianza: valida salida, aplica tope de 50.000
├── tools/
│   ├── budget.py         · context.budget
│   └── lookup.py         · canon.lookup, con control de presupuesto
├── app.py                · composición FastAPI: monta el router de cada funcionalidad
└── routes.py             · POST /novels/{id}/run, GET /novels/{id}
```

| Requisitos | RF-13 a RF-24, RF-91 a RF-100, RF-107, RNF-01 a RNF-09, RNF-24 |
|---|---|
| **Puerta** | Los invariantes de `verification.md` §7 comprobados por model checking |

**`dispatch.py` concentra el riesgo del sistema entero.** Es donde el texto de un modelo se convierte en objeto tipado. Todo lo que pase de ahí sin validar contamina el canon, y no hay revisión humana detrás que lo detecte.

---

## 3. Lo que se construye en cada tramo aunque no lo parezca

Tres cosas son transversales y **no tienen tramo propio a propósito**. Dejarlas para el final es la forma conocida de que no se hagan.

| Qué | Cuándo | Por qué no al final |
|---|---|---|
| **Rutas HTTP** | Cada tramo añade las suyas dentro de su carpeta | Concentrarlas al final deja los ocho tramos anteriores sin forma de ejercitarse |
| **Trazas a Langfuse** | Cada llamada, desde la primera | Es el único mecanismo para detectar que algo lleva diez capítulos degradándose (RNF-13) |
| **La regla de importación** | Desde el primer commit, en CI | Ver §1.2 |

---

## 4. Definición de terminado

Los ocho tramos compilando no es terminado. Esto sí:

- [ ] Los ocho tramos pasaron su puerta
- [ ] La puerta de CI del SRS §7.2 en verde
- [ ] Todo requisito con su método principal ejecutándose, o en el riesgo aceptado del SRS §7.4
- [ ] **Una tirada completa va del brief al cierre de obra sin intervención** (RNF-03)
- [ ] Copiar el fichero de la novela y abrirlo da las mismas proyecciones y la misma recuperación (RD-12)

El cuarto es el que cuenta. Los demás comprueban que el camino existe; ese comprueba que funciona.

---

## 5. Lo que queda por decidir antes de arrancar

Una sola cosa, y hay que cerrarla antes de indexar el primer capítulo:

**Qué variante multilingüe de `fastembed` puebla el índice.** El mecanismo está fijado (D-22) y el esquema guarda modelo y dimensión, así que cambiarlo después es reindexar y no rediseñar. Pero arrancar con un modelo monolingüe inglés degrada la pierna semántica desde el capítulo 1, y la degradación no dispara ninguna puerta: el sistema parece sano y recupera mal.
