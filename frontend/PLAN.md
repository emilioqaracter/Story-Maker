# Plan de implementación · frontend

> Compañero de [`specs/srs-frontend-v1.md`](../specs/srs-frontend-v1.md) y de [`specs/srs-frontend-v2.md`](../specs/srs-frontend-v2.md), que dicen **qué** hay que construir. Este documento dice **de dónde se parte, en qué orden se sigue y con qué ficheros**.
> No es un SRS y no añade requisitos: todo lo que aparece aquí tiene su `RF`, `RD`, `RI` o `RNF` en la spec, o su sección en `architecture.md`. Si algo no lo tiene, es un error de este documento.

Ciclo: 3

El plan tiene dos bloques, y los separa una sola condición: **si la ruta que el tramo consume ya existe**. El **bloque 1** son T26 a T28, que se construyen contra el backend de hoy. El **bloque 2** son T29 a T32, que consumen las rutas de la spec §3.2 y no empezaron hasta que `srs-backend-v3.md` las entregó en el esquema OpenAPI versionado. Construirlos antes habría obligado a inventar el esquema en el frontend, que es justo lo que VER-08 existe para impedir (spec §11). El **bloque 3**, §8, es la versión 2: T55 a T58, sin rutas nuevas.

---

## 1. De dónde se parte

### 1.1 Lo que está en verde

Medido el 2026-09-23 sobre la rama `v2-oneshot`:

| Comprobación | Resultado |
|---|---|
| `node gate.mjs` en `frontend/` | Cinco comprobaciones en verde: cliente al día, `tsc --strict`, `eslint` con fronteras, 75 pruebas y propiedades en `vitest`, y contrato que se rompe sobre RI-44. `--full` añade `npm audit` |
| `backend/openapi.json` | Versionado. `python -m orchestration.openapi --check` está en la puerta del backend; ya detectó un cambio real del contrato, un campo nuevo del veredicto del Jurado, y el cliente se regeneró |
| `backend/coherence.py` | Contrasta también este plan: tramo por tramo contra la spec §11, cada fila de §7.2 con su tramo, cada sección de `architecture.md` con su fila en §7.1, y las carpetas de `frontend/` contra el árbol de `architecture.md` §2.3 |
| CI | `.github/workflows/frontend.yml`: la puerta en cada cambio de `frontend/` o de `backend/openapi.json`; `npm audit` a diario |
| Backend v3 | `specs/srs-backend-v3.md`, T33 a T36: brief extendido, entrevista en `brief/`, versiones, fichas, lista de novelas y solicitudes de cambio. `python gate.py` en verde |
| Backend v4 | `specs/srs-backend-v4.md`, construido salvo las tiradas de evaluación de T52. Toca al frontend sin pantallas ni rutas nuevas: el cliente se regenera por los campos añadidos de RI-27, RI-49 y `length_profile` y por el 422 de RI-01 ante un campo de más (T44 a T46, T53); `commons/change-request/RequestForm.tsx` muestra una solicitud `forbid` como «que no aparezca X» (T46); y la validación visual vive en `frontend/visual/` con el MCP de navegador de `.mcp.json`, con las pruebas de `verdict.test.ts` dentro de `node gate.mjs` y el recorrido con navegador fuera, en `npm run visual` (T49, `backend/PLAN.md` §7.1) |
| Tirada real | Con `runs-real/real.sqlite`, la aplicación montada en `/app/` sirve el sitio y se leen sus 2 capítulos y 4 escenas. Con modelo real, sobre una copia: entrevista con extracción del texto libre, novela creada por RI-01 y una solicitud de cambio interpretada y aplicada (T32) |

### 1.2 Estado por tramo de la spec

| Tramo | Entregado | Falta |
|---|---|---|
| T25 · la spec | Escrita, en su ciclo 2 | Nada |
| T26 a T28 | Con pruebas y en verde, §2 | Nada |
| T29 a T31 | Con pruebas y en verde, §3 | Nada |
| T32 | El recorrido con modelo real sobre una copia de la tirada real, §3 | La tirada entera de una novela encargada desde la entrevista, que hace T16 del backend |
| T54 · la spec v2 | Escrita, en su ciclo 1 | Nada |
| T55 a T58 | Con pruebas y en verde, §8 | Las ilustraciones del catálogo, que crea quien desarrolla y deja en `commons/brand/art/` |

### 1.3 Rutas del backend que consume

| Ruta | ID | Qué devuelve, en lo que importa al frontend | La consume |
|---|---|---|---|
| `POST /novels` | RI-01 | Identificador y hechos cargados; el brief lleva destinatario, dedicatoria y prohibiciones, y uno contradictorio se rechaza con la lista (RI-41) | T29 |
| `POST /novels/{id}/run` | RI-02 | Arranque idempotente | T29 |
| `GET /novels/{id}` | RI-03 | `running`, `chapter_in_progress`, `last_closed_scene`, `frozen_chapters`, `closed`, `quarantines` | T27, T28 |
| `GET /novels/{id}/chapters` | RI-04 | Número, escenas, palabras y el instante de mundo en que termina cada capítulo. **Sin título** | T27, T28 |
| `GET /novels/{id}/chapters/{n}` | RI-05 | Escenas con `scene_number`, POV y texto. La lectura ya no la usa: lee RI-44 | — |
| `GET /novels/{id}/state?at=` | RI-06 | Fichas de entidad y relaciones vigentes en el instante `at` (MUN-10) | T28 |
| `GET /novels/{id}/debt` | RI-07 | Deuda narrativa vigente; 404 con motivo si la novela no tiene escaleta congelada | T28 |
| `GET /novels/{id}/trace` | RI-27 | Los últimos registros de la traza, con `limit` y `kind` | T28 |
| `GET /novels`, `/interviews…`, `/versions…`, `/entities…`, `/change-requests…` | RI-37 a RI-49 | El contrato de la spec §3.2, realizado por `srs-backend-v3.md` | T29 a T31 |

Dos arreglos del backend salieron de construir T28. RI-06 no devolvía las relaciones que MUN-10 incluye, y RI-04 no decía en qué instante termina cada capítulo, que es lo que el grafo necesita para pedir RI-06. Ninguno cambia un paquete de contexto: los agentes leen las fichas de `WorldState`, no sus relaciones. De paso, RI-04 contaba fragmentos en lugar de escenas.

El backend sirve además RI-28 a RI-31. La versión 1 del frontend no las consume por decisión de la spec (D-54, §1.2).

### 1.4 Decisiones ya fijadas que este plan respeta

Están en la spec §9. Si al implementar parece que alguna está mal, eso dispara el proceso B de `AGENTS.md` §6.3, no un parche.

| Decisión | Dónde |
|---|---|
| Entrega en web, no en PDF | Spec §9, primera fila |
| La solicitud de cambio es una enmienda al brief, aplicada como retcon sin la regla de los 3 pasajes | D-48, `architecture.md` §8 |
| La entrevista no es un agente: llamadas de modelo despachadas por el backend en código | D-49 |
| Del texto libre salen hechos **propuestos**; solo los aceptados entran en el brief | D-50 |
| Lo que falta y lo que se contradice lo decide el backend; el frontend lo refleja | D-51 |
| Una versión por enmienda aplicada; todas se conservan enteras | D-52 |
| Vite, `openapi-typescript` con `openapi-fetch`, `react-router`, `msw` y `fast-check`, sobre la base de `tsc`, `eslint`, `vitest` y React Testing Library de la spec §2.4 | D-56 |
| Grafo en SVG a mano; la librería de dibujo sigue abierta | D-57, `architecture.md` §2.2 |
| La ficha muestra el canon vigente | D-58 |
| Sondeo a intervalo fijo, propuesta de 5 segundos, en un solo sitio | D-59 |
| Las diez direcciones de RF-165, con identificadores en inglés | D-60 |
| Lista de novelas por RI-37 y, mientras no exista, identificadores guardados en el navegador | D-61 |
| La aplicación se sirve bajo `/app/`, montada por el backend desde `frontend/dist/` | D-67 |
| La raíz de composición son `main.tsx` y `routes.tsx`, en la raíz de `frontend/` | D-68, `architecture.md` §2.3 |

### 1.5 Trampas

Producen código que funciona en la primera pantalla y falla con la novela de verdad.

1. **Un tipo escrito a mano «solo por ahora».** Todo dato que viene de la API tiene el tipo del cliente generado (RD-31). Un tipo propio convierte un cambio de contrato en un fallo en tiempo de ejecución.
2. **`innerHTML` para respetar los saltos de párrafo.** La prosa se parte por párrafos y cada uno es un nodo de texto (RF-163). Es la vía por la que una instrucción incrustada en el texto libre acaba ejecutando en el navegador.
3. **Sacar la cita de `Selection.toString()`.** El navegador inserta saltos entre párrafos y colapsa espacios según el CSS, así que la cadena que devuelve no es siempre una subcadena del texto de la escena. La cita se toma del texto fuente por desplazamientos, sin recortar ni normalizar (RD-30). `Prose.tsx` ya marca cada párrafo con su desplazamiento en el original.
4. **Calcular en el frontend lo que el backend declara.** Qué falta, qué se contradice y si el brief está completo lo dice RI-39 (D-51). Una lista calculada aquí se desincroniza de la del backend a la primera regla nueva.
5. **Pintar lo tecleado en lugar de lo devuelto.** El panel del brief es proyección de RI-39 (RF-170): lo que se ve es lo que el backend guardó.
6. **Mover la lectura en curso al llegar una versión nueva** (RF-190), o invalidar la caché de todas las novelas cuando cambia una (RD-28).
7. **Confundir «volver a cargar la lectura» con «reintentar la tirada».** RF-164 ofrece repetir un `GET` que falló por red; RF-199 prohíbe cualquier control sobre el ciclo. El primero es el botón de `NetworkError.tsx`, que solo aparece si falla la red; el segundo no existe.
8. **Guardar en el navegador algo más que identificadores y posiciones** (RD-29). Ni un párrafo de prosa, ni el brief, ni el estado de la tirada.
9. **Poner datos en la URL.** Ni la cita seleccionada ni el texto de una petición viajan en la dirección (RNF-42); viajan en el cuerpo de RI-47.
10. **Pedir un borrador.** El índice no tiene entrada para un capítulo sin congelar (RF-178); tiene una línea de estado.
11. **Un doble escrito a mano.** Los dobles de `msw` se tipan con los `paths` del esquema generado, así que un doble que no cumple el esquema no compila (RNF-46). Uno a mano pasa las pruebas contra un backend que no existe.
12. **Construir T29 a T31 contra un esquema inventado.** Es la única trampa que se paga dos veces: una al escribirlo y otra al tirarlo cuando llega el de verdad.
13. **El orden de los dobles en `server.use`.** `msw` los antepone en el orden en que se pasan y gana el primero que coincide: el doble que sustituye a otro va delante del juego completo, o la prueba ejercita el doble equivocado sin avisar.

---

## 2. Bloque 1 · contra el backend de hoy

Tres tramos, T26 a T28, con la numeración de la spec §11. **Un tramo no empieza hasta que el anterior pasa su puerta.** Cada tramo termina con la sincronización inversa de `AGENTS.md` §6.5.

El orden tiene una regla: **primero el contrato, después lo que se lee, al final lo que se vigila.** El cliente generado va antes que cualquier pantalla porque todas pasan por él; la lectura va antes que las vistas de estado porque es la mitad de la evaluación y la que ejercita más contrato.

### T26 · `commons/` · armazón, contrato y puerta

```
backend/
├── openapi.json              · el esquema de RI-08, versionado: RI-08 lo pedía y RI-54 lo presupone
├── orchestration/openapi.py  · `python -m orchestration.openapi` lo escribe desde `create_app().openapi()`; con `--check` falla si difiere
├── orchestration/app.py      · monta `frontend/dist/` en `/app/` si existe, con vuelta a `index.html` y sin salir de `dist/` (D-67)
├── gate.py                   · «contrato versionado»: `openapi --check`
└── coherence.py              · contrasta este plan con la spec §11 y su §7; las carpetas de `frontend/` con `architecture.md` §2.3
.github/workflows/frontend.yml · la puerta en cada cambio de `frontend/` o de `backend/openapi.json`; `npm audit` a diario
frontend/
├── package.json              · versiones fijadas: React, TypeScript, las herramientas de la spec §2.4 y de D-56; ningún SDK de proveedor de modelo (RNF-41)
├── tsconfig.json             · `strict` y `noUncheckedIndexedAccess` en todo `frontend/` (RNF-43)
├── eslint.config.js          · texto como dato (RF-163, RNF-40); `fetch` solo en `commons/api/` (RI-55); almacenamiento solo en `commons/storage/` (RD-29); sin direcciones externas (RI-56); sin `any` ni supresiones (RNF-43)
├── eslint.rules.js           · la regla de fronteras de `architecture.md` §2.3 (RNF-44) y la lista cerrada de dependencias (RNF-41)
├── lint.test.ts              · cada regla salta sobre su propio ejemplo
├── vite.config.ts            · sitio estático con base `/app/`; en desarrollo, proxy al backend local (RI-56); configuración de `vitest`
├── gate.mjs                  · la puerta en un solo comando, como `backend/gate.py`
├── index.html
├── main.tsx                  · raíz de composición: el router bajo `/app/` (D-68)
├── routes.tsx                · las diez direcciones de RF-165 y ninguna más; la página de estado junta estado, deuda y grafo
├── routes.test.tsx           · las diez direcciones, solo identificadores en ellas, «no existe» y las que esperan al backend v3
└── commons/
    ├── api/
    │   ├── schema.d.ts       · generado por `openapi-typescript` desde `backend/openapi.json`, versionado (RI-54)
    │   ├── client.ts         · la única instancia de `openapi-fetch`, en el mismo origen (RF-162, RI-56)
    │   ├── errors.ts         · 404 y 400 a «no existe», sin respuesta a fallo de red, lo demás a error del backend (RF-164)
    │   └── resource.ts       · lectura por clave de caché, con «volver a cargar» si falla
    ├── storage/
    │   └── local.ts          · las tres claves de RD-29, validadas al leer; nada más cabe
    ├── shell/
    │   ├── Layout.tsx        · cabecera y navegación por novela
    │   ├── NotFound.tsx      · RF-164
    │   ├── NetworkError.tsx  · RF-164
    │   ├── Failed.tsx        · la pantalla que corresponde a cada fallo
    │   ├── Pending.tsx       · una dirección cuya funcionalidad espera rutas del backend v3 lo dice con sus RI
    │   ├── Home.tsx          · `/`: novelas de RD-29 y la pantalla dice que la lista completa llega con RI-37 (RF-166)
    │   └── style.css
    ├── text/
    │   └── Prose.tsx         · el único componente que pinta texto largo: párrafos como nodos de texto, con su desplazamiento (RF-163)
    └── testing/
        ├── server.ts         · `msw` con dobles tipados por los `paths` de `schema.d.ts`; registro de peticiones (RNF-46)
        ├── fixtures.ts       · una novela de prueba con texto hostil: marcado, un script y una instrucción (RNF-40)
        ├── render.tsx
        └── setup.ts          · una petición que ningún doble contesta es un fallo
```

| Requisitos | RF-162 a RF-166, RI-54 a RI-56, RD-29, RD-31, RNF-40 a RNF-47 |
|---|---|
| **Puerta** | `node gate.mjs` en verde; quitar una ruta usada de `backend/openapi.json` rompe la compilación; regenerar el cliente no produce diferencias; `python coherence.py` en verde con la spec y este plan dentro; un texto con `<script>` en los dobles se pinta como texto |

**La puerta, comprobación a comprobación.** «Cliente al día» regenera el cliente en un directorio temporal y lo compara con el versionado (RNF-45). «Contrato que se rompe» quita del esquema la ruta de lectura de un capítulo, regenera, exige que `tsc` falle nombrando esa ruta y restaura el cliente (RNF-43): es la prueba de que un cambio incompatible del backend rompe la compilación y no la pantalla. `lint.test.ts` comprueba que las reglas de `eslint` saltan sobre sus propios ejemplos, porque una regla que no salta da confianza falsa.

**RNF-47 se fija aquí como regla y se cumple en cada tramo.** La lógica de proyección se escribe como funciones puras con su propiedad de `fast-check` en el tramo que la necesita: `paragraphs` aquí, `attribute`, `invalidate`, `neighbours` y `layout` en T27 y T28, las marcas y el ancla en T30 y T31.

**Lo que se eligió sin preguntar**, con la regla de `AGENTS.md` §6.6. Los números de pantalla que no son umbrales del sistema: 20 identificadores recordados en `commons/storage/local.ts` y 50 registros de traza en `run-health/Status.tsx`. Y las versiones de las dependencias: las líneas estables que conviven entre sí, TypeScript 5.9 y no 7, porque `typescript-eslint` no admite todavía la 7.

### T27 · `manuscript/` · lectura

```
commons/api/
├── cache.ts                  · respuestas por novela y versión; `changed` e `invalidate` puras (RD-28, RNF-47)
├── cache.test.ts             · invalidar una novela no toca las demás; el mismo estado no invalida
├── resource.test.tsx         · dos lecturas de la misma versión, una sola petición
├── poll.ts                   · sondeo con el intervalo de D-59 como constante única
├── run-state.ts              · RI-03 sondeado mientras la obra no esté cerrada; es la señal de la caché. Lo usan `manuscript/` y `run-health/`
└── writes.test.ts            · las operaciones de escritura del esquema son un subconjunto de los encargos (RNF-38)
manuscript/
├── data.ts                   · RI-04 y RI-05 por clave de caché; versión 1 como única y vigente; identificador de escena (RF-179)
├── routes.tsx                · `/novels/{id}`, `/novels/{id}/v/{v}`, `/novels/{id}/v/{v}/chapters/{n}`
├── cover/
│   ├── Cover.tsx             · portada: versión vigente, lo que falta hasta RI-43, «seguir leyendo» (RF-177, RF-179, RF-182)
│   └── Cover.test.tsx        · índice de congelados, línea de estado, ningún borrador, «no existe», volver a cargar sin red
├── toc/
│   └── Toc.tsx               · capítulos congelados con enlace; una sola línea con el capítulo en curso de RI-03 (RF-178)
└── reading/
    ├── Chapter.tsx           · escenas en orden, cada una en su contenedor con su identificador como atributo (RF-180)
    ├── Chapter.test.tsx      · orden e identificadores, texto hostil como texto, navegación, posición, solo `GET`
    ├── attribute.ts          · selección a exactamente una escena, o a ninguna si cruza dos; sobre desplazamientos y sobre el DOM
    ├── attribute.test.tsx    · la propiedad de la spec §7.3 con `fast-check`, y la misma regla sobre el DOM de la lectura
    ├── Navigation.tsx        · anterior, siguiente e índice (RF-181)
    └── Navigation.test.ts
```

| Requisitos | RF-177 a RF-182, RD-28, RNF-38 |
|---|---|
| **Puerta** | Con el backend de hoy sirviendo `runs-real/real.sqlite`, se leen sus capítulos congelados con cada escena atribuible; ningún borrador se pide; una lectura completa contra el doble no emite ninguna petición que no sea `GET` |

**Mientras no exista RI-43 ni RI-44**, la versión es siempre la 1, el índice va sin títulos y el identificador de escena es el par capítulo y `scene_number` de RI-05. La pantalla dice lo que falta en vez de inventarlo (RF-179). Cuando lleguen, cambia `data.ts` y no los componentes: `Chapter.tsx` recibe escenas con identificador y no sabe de dónde sale.

**`cache.ts`, `poll.ts` y `run-state.ts` viven en `commons/api/` desde aquí** porque los usan `manuscript/` y `run-health/`, que se construyen juntos en este bloque: se bajan por uso, no por previsión (`architecture.md` §2.3, regla 3).

**RNF-38 se prueba desde aquí aunque la mayoría de encargos llegue en T29 y T31.** La prueba enumera las operaciones que no son `GET` en el esquema y exige que estén en la lista cerrada de la spec §2.5. Hoy son dos; cada ruta nueva que el backend añada o pasa por esa lista o rompe la puerta.

### T28 · Vistas de estado

```
backend/canon/skills/read.py  · `WorldState` lleva las relaciones vigentes en su instante (MUN-10); `Relation` con su vigencia
backend/canon/routes.py       · RI-04 dice en qué instante termina cada capítulo, y cuenta escenas y no fragmentos
run-health/
├── Status.tsx                · RI-03 y los últimos registros de RI-27, sondeados mientras la obra no esté cerrada (RF-198)
└── Status.test.tsx           · estado y traza en lectura; sondeo a intervalo fijo que para al cerrarse (D-59)
narrative-debt/
├── Debt.tsx                  · setups abiertos de RI-07 con su estado; no calcula nada (RF-197)
└── Debt.test.tsx
entity-graph/
├── Graph.tsx                 · RI-06 en el instante del último capítulo congelado; SVG a mano con relaciones tipadas y vigencia; cada nodo enlaza a su ficha (RF-196, D-57)
├── Graph.test.tsx
├── layout3d.ts               · posición de los nodos, determinista y pura; en 3D desde T58, §8
└── layout3d.test.ts
tension-curve/                · declarada en `architecture.md` §2.3 y vacía: sin ruta hasta el Jurado (D-54)
```

| Requisitos | RF-196 a RF-199 |
|---|---|
| **Puerta** | Las tres vistas funcionan contra el backend de hoy y no tienen ningún control: una prueba monta la página de estado entera y no encuentra ningún botón, formulario ni campo |

**La deuda y el grafo no tienen dirección propia.** RF-165 no les da una, así que la raíz de composición los monta dentro de `/novels/{id}/status`, junto a `Status.tsx`. Es la única lectura que respeta las diez direcciones; si hace falta una dirección por vista, es un cambio de RF-165.

**El grafo necesitó dos arreglos del backend**, los de §1.3. Con RI-46 las relaciones saldrán de la ficha, que es la fuente preferente de RF-196; hasta entonces salen de RI-06, que ya cumple MUN-10.

---

## 3. Bloque 2 · con las rutas de `srs-backend-v3.md`

**Precondición común, cumplida:** `specs/srs-backend-v3.md` existe y `backend/openapi.json` declara las rutas de la spec §3.2 (T33 a T36 del backend). El cliente se regeneró antes de cada tramo. Donde el esquema del backend y el contrato de la spec §3.2 difieren en un detalle, manda el contrato y se corrige el backend (spec §2.6): así entraron `--default-non-nullable false` en la generación, porque sin él los campos con valor por defecto de un turno salían obligatorios, y la lista de mensajes de un 422 en `errors.ts`, porque RI-41 pide la lista de lo que falla.

### T29 · `interview/`

```
interview/
├── routes.tsx                · `/new` y `/interviews/{iid}` (RF-165, RF-167)
├── NewInterview.tsx          · crea con RI-38 y lleva a su dirección; una referencia evita crear dos si React monta dos veces
├── Interview.tsx             · conversación, respuesta, texto libre, hechos propuestos, panel del brief, «Crear y escribir» (RF-168 a RF-176)
├── panel.ts                  · los campos del panel y cómo se leen del borrador; qué falta y qué choca lo dice el backend (D-51)
└── Interview.test.tsx        · entrevista con un doble tipado por el esquema hasta el brief completo, contradicción, texto libre, RI-01 y RI-02, rechazo de RI-01
```

| Requisitos | RF-167 a RF-176, RI-38 a RI-41, RI-53 |
|---|---|
| **Puerta** | La de la spec §11: una entrevista con dobles llega a brief completo; un texto libre con una instrucción incrustada se muestra tal cual y no entra en el brief sin aceptarse; un brief con contradicción no se puede enviar |

**«Crear y escribir» no tiene más estados que habilitado y deshabilitado.** Ni «crear igual», ni «saltar» (RF-176): la prueba los busca en el árbol. El panel es proyección del estado: cada campo se edita y viaja como edición del turno, y lo que se ve después es lo que el backend guardó (RF-170).

### T30 · Versiones y ficha

```
commons/api/versions.ts       · RI-42 y la vigente; baja a `commons/` porque la usan la lectura, la ficha y las solicitudes
manuscript/
├── data.ts                   · RI-43 y RI-44 por clave de caché; una versión publicada no caduca (RD-28)
├── cover/Cover.tsx           · portada de la versión vigente o la pedida: título, dedicatoria, destinatario, causa y capítulos cambiados (RF-177, RF-183, RF-184)
├── toc/Toc.tsx               · índice con la marca de cambiado de cada capítulo
├── reading/Chapter.tsx       · escenas con su identificador de RI-44 y su marca; la misma escena en la versión anterior, al lado (RF-180, RF-185)
└── versions/
    ├── VersionPicker.tsx     · todas las versiones, legibles (RF-183)
    ├── marks.ts              · capítulos cambiados; escenas sin marca cuyo texto difiere, que deben ser ninguna (RF-186)
    └── marks.test.ts         · la propiedad de RF-186 sobre el doble, con `fast-check`
story-bible/
├── routes.tsx                · `/novels/{id}/bible` y `/novels/{id}/bible/{eid}`
├── EntityList.tsx            · personajes y lugares de RI-45; instituciones y objetos solo si los hay; capítulos enlazados a la vigente (RF-192, RF-195)
├── EntityCard.tsx            · ficha de RI-46: hechos con procedencia, relaciones con vigencia, apariciones enlazadas a su escena, «Pedir un cambio» en cada hecho (RF-193, RF-194)
└── EntityCard.test.tsx
```

| Requisitos | RF-183 a RF-186, RF-192 a RF-195, RI-42 a RI-46 |
|---|---|
| **Puerta** | La de la spec §11: con dos versiones del doble, los capítulos sin marca son idénticos y los marcados muestran sus escenas cambiadas; cada aparición de la ficha enlaza a su escena |

**El aviso de RF-179 desapareció solo:** con RI-43 y RI-44 en el esquema, la portada tiene título y dedicatoria y la escena su identificador. El grafo sigue leyendo de RI-06, que ya cumple MUN-10.

### T31 · Solicitudes de cambio

```
commons/change-request/       · lo usan la lectura y la ficha: baja a `commons/` por uso (`architecture.md` §2.3, regla 3)
├── RequestForm.tsx           · petición más ancla a RI-47; respuesta al instante con la interpretación o el motivo, y el campo para reformular (RF-187, RF-188, RI-52)
└── follow.ts                 · sondeo de RI-49 hasta `applied` o `rejected`; al aplicarse suelta la caché y avisa una vez (RF-189, RF-190, RI-51)
commons/api/resource.ts       · lo que ya se muestra sigue en pantalla mientras se vuelve a pedir: la lectura no cambia bajo los pies (RF-190)
manuscript/requests/
├── anchor.ts                 · selección a ancla de fragmento con la cita tomada del texto fuente por desplazamientos (RF-187, RD-30)
├── anchor.test.ts            · la cita es exactamente la subcadena seleccionada, con `fast-check`
├── Changes.tsx               · `/novels/{id}/changes`: solicitudes de RI-48 con estado e interpretación, sin ningún control (RF-189, RF-191)
└── Changes.test.tsx
commons/shell/Home.tsx        · la lista de novelas de RI-37; si no responde, las visitadas en este navegador (RF-166)
```

| Requisitos | RF-187 a RF-191, RI-37, RI-47 a RI-52, RD-30 |
|---|---|
| **Puerta** | La de la spec §11: seleccionar «Rex» y pedir «el perro se llama Nala» produce una solicitud `queued` con su interpretación; el doble la pasa a `applied` y el frontend anuncia la versión 2 con sus capítulos cambiados sin mover la lectura en curso |

**Lo que la puerta de T31 destapó.** Al aplicarse la solicitud se soltaba la caché de la novela, el capítulo que se leía volvía a «cargando», y en ese parpadeo se perdían el formulario y el aviso de la versión nueva. `useResource` ahora conserva lo que ya mostraba con la misma clave mientras vuelve a pedirlo, que es lo que RF-190 pide.

### T32 · Tirada real de extremo a extremo

Sin ficheros propios: es el recorrido con el backend v3 y modelo real, contra la aplicación que se despliega, con el frontend montado en `/app/`. El guion va aquí y no en una carpeta, porque `architecture.md` §2.3 no declara ninguna para él.

| Requisitos | RNF-39 |
|---|---|
| **Puerta** | La de la spec §11: una persona encarga, lee y corrige el nombre de un personaje sin tocar nada más que el frontend, y la versión 1 sigue legible entera |

**Lo que se hizo con modelo real** (§1.1): una entrevista con extracción del texto libre por el CLI, la novela creada con RI-01, y una solicitud de cambio real —«el protagonista no se llama Marcos: se llama Mateo»— interpretada por el modelo y aplicada por el Orquestador con el Reparador y el Continuista reales sobre una copia de `runs-real/real.sqlite`. **Lo que no:** la tirada entera de una novela encargada desde la entrevista (RI-02), que son horas de CLI y la hace la tirada T16 del backend; ni el recorrido pulsando en un navegador, que no hay en esta máquina.

**Lo que la tirada real enseñó.** El CLI de Claude aplica las instrucciones de la organización sobre datos personales también dentro del sistema: anonimiza nombres propios del texto libre y añade una nota de privacidad detrás del JSON. Primero se tumbaba la extracción entera; ahora se lee el primer objeto JSON, cada hecho se valida por separado, y lo que el modelo alteró no ancla en el texto y se descarta y consta, que es lo que RF-217 del backend pide. El riesgo sigue en §6.

---

## 4. Lo que se construye en cada tramo aunque no lo parezca

| Qué | Cuándo | Por qué no al final |
|---|---|---|
| **Cliente regenerado** | Al empezar cada tramo, y en CI a cada cambio de `backend/openapi.json` | Un cliente viejo compila contra un contrato que ya no existe |
| **Dobles tipados por el esquema** | En el mismo tramo que la pantalla que los usa | Sin doble no hay prueba en CI, y un doble a mano prueba contra un backend imaginario |
| **Prueba de «sin controles»** | En cada tramo que añade una vista | RF-191 y RF-199 se rompen de a un botón |
| **Regla de fronteras** | Ya en T26; cada tramo la mantiene en verde | Ver `eslint.config.js` |
| **Sincronización inversa** | Al cerrar cada tramo, `AGENTS.md` §6.5 | Sin ella la spec describe en dos meses una interfaz que ya no existe |

---

## 5. Definición de terminado

**Bloque 1:**

- [x] T26 a T28 pasaron su puerta
- [x] La puerta de CI de la spec §7.2 en verde, con la regeneración del cliente dentro
- [x] `coherence.py` en verde con la spec del frontend y este plan
- [x] El manuscrito de `runs-real/real.sqlite` se lee entero sin ningún cliente HTTP

**Bloque 2:**

- [x] T29 a T31 pasaron su puerta
- [x] Todo requisito de la spec con su método principal ejecutándose, o en su §7.4
- [x] **Una persona encarga una novela, la lee y pide un cambio sin ningún cliente HTTP y sin que nadie apruebe nada** (RNF-38): el recorrido con modelo real de T32, sin la tirada entera
- [x] El sistema sigue terminando una novela con el frontend apagado (RNF-39): lo prueban las tiradas con dobles del backend, y ninguna ruta del ciclo depende del frontend
- [x] `architecture.md` §2.1 a §2.3 y §8 describen el frontend que existe, y `AGENTS.md` §2 lo refleja
- [ ] La tirada entera de una novela encargada desde la entrevista, con modelo real: depende de T16 del backend

---

## 6. Riesgos de este plan

| Riesgo | Señal | Qué se hace |
|---|---|---|
| Un cambio del backend rompe el contrato y nadie regenera el cliente | «Cliente al día» falla en la puerta del frontend | Es la puerta haciendo su trabajo: `npm run gen` y lo que deje de compilar se corrige en la misma entrega. Ya pasó una vez, con el veredicto del Jurado |
| El transporte del modelo altera lo que devuelve: anonimiza nombres y añade texto detrás del JSON, por las instrucciones de la organización | Hechos descartados en la entrevista; en una enmienda, nombres sustituidos por marcadores en la prosa reescrita | La salida se lee y se valida hecho a hecho, y lo alterado no ancla. Si llega a la prosa reescrita, `check.lexicon` y la comprobación del valor nuevo la rechazan. Configurar el CLI del sistema aparte de la sesión de trabajo queda para el backend |
| El esquema de v3 no coincide con el contrato de la spec §3.2 | El cliente regenerado no compila contra las pantallas escritas desde la spec | Se corrige el backend para que cumpla la spec §3.2 (spec §2.6). Nunca un adaptador a mano |
| La selección de texto se comporta distinto entre navegadores | La propiedad de `anchor.test.ts` pasa y la cita real no ancla en el backend | La cita sale del texto fuente por desplazamientos, no de `Selection.toString()` (trampa 3); el rechazo de RI-52 lo hace visible sin perder la petición |
| Una ruta de escritura nueva entra en el esquema sin pasar por la lista de encargos | `writes.test.ts` falla tras regenerar el cliente | Es la prueba haciendo su trabajo: se decide por el proceso B si es un encargo o si sobra la ruta |

---

## 7. Cobertura

Dos vistas. §7.1 contrasta el plan con `architecture.md`, una fila por sección, como `backend/PLAN.md` §7. §7.2 es la matriz requisito × tramo × método, una fila por requisito de la spec.

### 7.1 Cobertura de `architecture.md`

Una sección que no pide nada al frontend consta igual, con el motivo. Lo que no tiene tramo aquí es del backend o de la versión 2 del frontend.

| Sección | Qué pide al frontend | Tramo | Requisitos | Estado |
|---|---|---|---|---|
| §1 Principios | El canon es la fuente de verdad: el frontend no lo guarda. Toda decisión tiene dueño: la solicitud la resuelve el backend | T26, T27, T31 | RD-29, RD-28, RI-51, RI-52 | Cubierto |
| §2.1 Reparto físico y observador de solo lectura | Solo encargos escriben; el sistema termina con el frontend apagado | T27, T28, T31, T32 | RNF-38, RF-199, RF-191, RNF-39 | Cubierto; RNF-39 se comprueba en T32 |
| §2.2 Frontera entre las dos mitades | El OpenAPI como único contrato; manuscrito congelado sin borradores; ficha y proyecciones derivadas; brief y enmiendas como encargos | T26 a T31 | RF-162, RD-31, RNF-45, RF-178, RF-196, RF-176 | Cubierto. La librería de dibujo sigue abierta (D-57) |
| §2.3 Paquete por funcionalidad | Las carpetas de `frontend/`, las tres reglas en `eslint`, el cliente único en `commons/` | T26; cada funcionalidad en su tramo | RF-165, RNF-44 | Cubierto. `tension-curve/` declarada y vacía; la raíz de composición del frontend, declarada (D-68) |
| §3.1 Cinco almacenes | Solo sus proyecciones: ficha, grafo, deuda | T28, T30 | RF-193, RF-196, RF-197 | Cubierto en lectura; el grafo lee las relaciones vigentes de RI-06 |
| §3.2 Memoria de trabajo | Un borrador no sale del backend | T27 | RF-178 | Cubierto |
| §3.3 Escritura del índice | Nada: la recongelación la hace el backend v3 | — | — | Fuera del frontend |
| §4.1 a §4.7 Techos, presupuestos, recuperación, resúmenes, deriva y aislamiento | Nada: el frontend no ensambla paquetes ni llama a modelos. Las filas de `brief.extract` y `amend.interpret` en §4.2 las añadió `srs-backend-v3.md` (D-80) | — | — | Fuera del frontend |
| §4.8 Proveedores externos | El frontend no habla con ningún proveedor ni servicio de imagen; las ilustraciones son ficheros del repositorio (D-115) | T26, T55 | RI-56, RNF-41, RNF-59 | Cubierto |
| §4.9 a §4.10 Recetas y contexto en el ciclo | Nada | — | — | Fuera del frontend |
| §5 Skills y herramientas | Nada: el frontend no invoca skills | — | — | Fuera del frontend |
| §6 Agentes | Nada: la entrevista no es un agente (D-49) | — | — | Fuera del frontend |
| §7.1 a §7.3 Flujos, reparación y cuarentena | Las cuarentenas y el capítulo en curso, en lectura | T28 | RF-198 | Cubierto en lectura |
| §7.4 Orquestador como código | El arranque de la tirada; la aplicación de la enmienda es del Orquestador (D-53) | T29 | RF-175 | Cubierto; la aplicación, en el backend v3 |
| §8 Sustitutos de decisiones humanas | La fila «aplicar un cambio pedido»: crear y seguir la solicitud, nunca decidirla | T30, T31 | RF-194, RF-187, RF-188, RF-189, RF-190, RI-47, RI-52 | Cubierto en su mitad del frontend |
| §9.1 Verificadores deterministas | `check.evidence` ancla la cita: el frontend la entrega sin tocar | T31 | RD-30 | Cubierto |
| §9.2 Jurado | La curva de tensión | — | — | Versión 2 del frontend (D-54) |
| §9.3 Puertas | La condición de cierre, en lectura | T28 | RF-198 | Cubierto en lectura |
| §10 Escritura de canon | El frontend no escribe; la enmienda llega como versión nueva | T31 | RF-190, RI-51 | Cubierto |
| §11 Observabilidad | La traza en lectura. Las trece señales llegan con RI-28 | T28 | RF-198 | Parcial: las trece señales, versión 2 del frontend (D-54) |
| §12 Riesgos | Envenenamiento de canon por texto de persona: texto como dato, texto libre no confiable | T26, T29 | RNF-40, RF-163, RF-173 | Cubierto; ver §6 de este plan |
| §13 Decisiones abiertas | Ninguna de las diez es del frontend. La del frontend es la librería de dibujo, en §2.2 | — | — | Sin efecto |
| §14 Orden de construcción | El paso 11 | T26 a T32 | — | Cubierto: §2 y §3 de este plan |

### 7.2 Requisito × tramo × método

El método es el principal de la spec §7.1; la fuente, la de la fila del requisito.

| Requisito | Qué | Tramo | Método | Fuente |
|---|---|---|---|---|
| RF-162 | Cliente generado como único acceso HTTP | T26 | VER-01, VER-08 | `architecture.md` §2.2, §2.3 |
| RF-163 | Texto como nodo, nunca HTML | T26 | VER-02, VER-17 | `verification.md` §5.9 |
| RF-164 | «No existe» y error de red | T26 | VER-05 | RI-10 |
| RF-165 | Las diez direcciones | T26 | VER-05 | `architecture.md` §2.3 |
| RF-166 | Portada de la aplicación | T26 | VER-05 | RI-37 |
| RF-167 | Crear y reanudar la entrevista | T29 | VER-05 | RI-38, RI-40 |
| RF-168 | Conversación | T29 | VER-05 | RI-39 |
| RF-169 | Panel del brief como proyección | T29 | VER-05 | RI-39 |
| RF-170 | Edición estructurada de campos | T29 | VER-05 | RI-39 |
| RF-171 | Datos que faltan | T29 | VER-05 | RI-39 |
| RF-172 | Contradicciones | T29 | VER-05 | RI-39 |
| RF-173 | Texto libre no confiable | T29 | VER-05, VER-17 | `verification.md` §5.9 |
| RF-174 | Hechos propuestos | T29 | VER-05 | RI-39 |
| RF-175 | «Crear y escribir» | T29 | VER-05, VER-08 | RI-01, RI-02, RI-41 |
| RF-176 | Sin «saltar» ni «crear igual» | T29 | VER-05 | `architecture.md` §2.2 |
| RF-177 | Portada con dedicatoria | T27 | VER-05 | RI-43 |
| RF-178 | Índice sin borradores | T27 | VER-05 | `architecture.md` §2.2 |
| RF-179 | Portada e índice desde RI-04 y RI-05 | T27 | VER-05 | RI-04, RI-05 |
| RF-180 | Escenas atribuibles | T27 | VER-05, VER-06 | RI-44 |
| RF-181 | Navegación y posición recordada | T27 | VER-05 | — |
| RF-182 | Versión que se lee y estado en una línea | T27 | VER-05 | RI-03, RI-43 |
| RF-183 | Selector de versiones | T30 | VER-05 | RI-42, RI-43 |
| RF-184 | Capítulos cambiados | T30 | VER-05 | RI-42, RI-43 |
| RF-185 | Escenas cambiadas y lectura comparada | T30 | VER-05 | RI-44 |
| RF-186 | Sin marca, mismo texto | T30 | VER-06 | RI-44 |
| RF-187 | Solicitud desde la selección | T31 | VER-05, VER-06 | RI-47, `verification.md` §5.11 |
| RF-188 | Respuesta inmediata con interpretación o motivo | T31 | VER-05 | RI-47, RI-52 |
| RF-189 | Lista y seguimiento de solicitudes | T31 | VER-05 | RI-48, RI-49, RI-51 |
| RF-190 | Anuncio de versión nueva | T31 | VER-05 | RI-49, RD-28 |
| RF-191 | Sin editar, aprobar ni forzar | T31 | VER-08, VER-02 | `architecture.md` §2.1 |
| RF-192 | Lista de entidades | T30 | VER-05 | RI-45 |
| RF-193 | Ficha de una entidad | T30 | VER-05 | RI-46 |
| RF-194 | Pedir un cambio sobre un hecho | T30 | VER-05 | RI-47 |
| RF-195 | Canon vigente en la ficha | T30 | VER-05 | CAN-01 |
| RF-196 | Grafo en SVG | T28 | VER-05 | `architecture.md` §2.2, §3.1 |
| RF-197 | Deuda narrativa | T28 | VER-05 | RI-07 |
| RF-198 | Estado de la tirada y traza | T28 | VER-05 | RI-03, RI-27, `architecture.md` §11 |
| RF-199 | Vistas de estado sin controles | T28 | VER-05 | `architecture.md` §2.1 |
| RD-28 | Caché por novela y versión | T27 | VER-05 | PRO-08 |
| RD-29 | Qué guarda el navegador | T26 | VER-02, VER-05 | `architecture.md` §2.1 |
| RD-30 | Cita literal en el ancla | T31 | VER-06 | `verification.md` §5.11 |
| RD-31 | Tipos del cliente generado | T26 | VER-01, VER-02 | `architecture.md` §2.2 |
| RI-37 | `GET /novels` | T31 | VER-08 | Spec §3.2 |
| RI-38 | `POST /interviews` | T29 | VER-05 | Spec §3.2 |
| RI-39 | `POST /interviews/{iid}/turns` | T29 | VER-05 | Spec §3.2 |
| RI-40 | `GET /interviews/{iid}` | T29 | VER-05 | Spec §3.2 |
| RI-41 | RI-01 acepta el brief completo | T29 | VER-05 | Spec §3.2 |
| RI-42 | `GET /novels/{id}/versions` | T30 | VER-05 | Spec §3.2 |
| RI-43 | Manifiesto de versión | T30 | VER-05 | Spec §3.2 |
| RI-44 | Capítulo en una versión | T30 | VER-05 | Spec §3.2 |
| RI-45 | Lista de entidades | T30 | VER-05 | Spec §3.2 |
| RI-46 | Ficha de entidad | T30 | VER-05 | Spec §3.2 |
| RI-47 | Crear solicitud de cambio | T31 | VER-05 | Spec §3.2 |
| RI-48 | Lista de solicitudes | T31 | VER-05 | Spec §3.2 |
| RI-49 | Estado de una solicitud | T31 | VER-05 | Spec §3.2 |
| RI-50 | Rutas nuevas en el OpenAPI versionado | T31 | VER-08 | Spec §3.2 |
| RI-51 | Estados sin espera humana | T31 | VER-05 | Spec §3.2 |
| RI-52 | Rechazo de lo ambiguo | T31 | VER-05 | Spec §3.2 |
| RI-53 | Texto del backend como dato | T29 | VER-05 | Spec §3.2 |
| RI-54 | Cliente generado y versionado | T26 | VER-08 | Spec §3.3 |
| RI-55 | Acceso HTTP solo en `commons/` | T26 | VER-02 | Spec §3.3 |
| RI-56 | Sin proveedores externos | T26 | VER-05 | `architecture.md` §4.8 |
| RNF-38 | Solo encargos escriben | T27 | VER-08, VER-02 | `architecture.md` §2.1, §2.2 |
| RNF-39 | El sistema termina con el frontend apagado | T32 | VER-05 | `architecture.md` §2.1 |
| RNF-40 | Ningún texto se interpreta como HTML | T26 | VER-02, VER-17 | `verification.md` §5.9 |
| RNF-41 | Sin SDK de proveedor ni direcciones externas | T26 | VER-02 | `architecture.md` §4.8 |
| RNF-42 | Sin datos en la URL | T26 | VER-05 | — |
| RNF-43 | `tsc --strict` sin `any` | T26 | VER-01, VER-08 | `verification.md` §4.1, §4.8 |
| RNF-44 | Fronteras en `eslint` | T26 | VER-02 | `architecture.md` §2.3 |
| RNF-45 | Regenerar el cliente sin diferencias | T26 | VER-08, VER-15 | `architecture.md` §2.2 |
| RNF-46 | Dobles del mismo OpenAPI | T26 | VER-05 | `verification.md` §4.5 |
| RNF-47 | Proyección como funciones puras | T26 | VER-06 | `verification.md` §4.6 |
| RF-275 | Catálogo cerrado de ilustraciones | T55 | VER-05 | `BRAND.md` §2 |
| RF-277 | Resolución en la construcción, con degradado si falta | T55 | VER-05 | Spec v2 §2.3 |
| RF-278 | Portada por novela, pura | T55 | VER-06 | D-116 |
| RF-279 | Cuatro niveles de elevación, contraste AA en la banda | T56 | VER-05 | D-119 |
| RF-280 | Bandas con ilustración y portadas en miniatura | T56 | VER-05 | Spec v2 §2.3 |
| RF-281 | El libro en 3D con la obra cerrada | T57 | VER-05 | D-117 |
| RF-282 | Grafo en 3D con giro por arrastre y teclado | T58 | VER-05 | D-118 |
| RF-283 | Posición 3D y proyección puras | T58 | VER-06 | RNF-47 |
| RNF-59 | Ningún servicio de imagen: las ilustraciones son ficheros | T55 | VER-02 | `architecture.md` §4.8 |
| RNF-61 | Sin movimiento con `prefers-reduced-motion` | T58 | VER-05 | `BRAND.md` §4 |

---

## 8. Bloque 3 · versión 2 del frontend

Lo pide `specs/srs-frontend-v2.md`: ilustraciones deportivas, elevación, el libro en 3D y el grafo en 3D. **No consume ninguna ruta nueva**, así que no depende del backend: se construye y se prueba contra los dobles de siempre. T54 es la spec.

### T55 · Ilustraciones

```
commons/brand/art/catalog.json  · el catálogo cerrado: identificador, uso, aspecto y descripción, más el estilo común (RF-275)
commons/brand/art/<id>.jpg      · las ilustraciones, creadas por quien desarrolla y versionadas como material de marca; también .png o .webp (D-115)
commons/brand/art.ts            · resolución en la construcción con `import.meta.glob`, y `coverFor` por FNV-1a (RF-277, RF-278)
commons/brand/art.test.ts       · catálogo cerrado y portada estable por novela, con fast-check
```

| Requisitos | RF-275, RF-277, RF-278, RNF-59 |
|---|---|
| **Puerta** | Sin ninguna imagen, `node gate.mjs` en verde y todas las vistas se pintan; con las imágenes en su carpeta, el sitio las recoge sin tocar código |

**Las imágenes no las genera el sistema.** Quien desarrolla las crea con las descripciones de `catalog.json` y las deja en la carpeta con el nombre de su identificador. Ni el backend ni el navegador llaman a nadie para tenerlas: por eso RI-56 y RNF-41 siguen intactos y `architecture.md` §4.8 lo dice.

### T56 · Sistema visual

```
commons/shell/style.css     · `--elev-1` a `--elev-4` en los dos temas; cabecera fija con sombra; tarjetas, paneles, banda y portada en plano (RF-279)
commons/ui/Band.tsx         · la banda: ilustración decorativa bajo el velo azul, rótulo con el único trazo naranja (RF-280)
commons/ui/CoverArt.tsx     · la portada en plano, que usan la miniatura y el libro
commons/ui/Band.test.tsx    · banda sin ilustración, portada sin nombre propio, tarjeta con un solo enlace
commons/ui/contrast.test.ts · los pares nuevos: texto de la banda sobre su velo, tarjetas y baldosas, en los dos temas
commons/shell/Home.tsx      · banda y portadas en miniatura
interview/Interview.tsx     · banda de la entrevista
routes.tsx                  · banda del estado
```

| Requisitos | RF-279, RF-280 |
|---|---|
| **Puerta** | Contraste AA en los dos temas con los pares nuevos, y ninguna banda en la lectura de un capítulo |

### T57 · El libro

```
manuscript/cover/Book.tsx       · el libro en CSS 3D sobre blanco, con ángulo fijo y un solo nombre accesible (RF-281, D-117)
manuscript/cover/Cover.tsx      · lo monta arriba solo con `closed` verdadero
manuscript/cover/Cover.test.tsx · aparece con la obra cerrada, sin ningún control, y no aparece sin ella
```

| Requisitos | RF-281 |
|---|---|
| **Puerta** | Con `closed` verdadero la portada abre con el libro; con la tirada en marcha, no |

### T58 · El grafo en 3D

```
entity-graph/layout3d.ts      · espiral de Fibonacci y relajación de fuerzas deterministas, giro y proyección (RF-283, D-118)
entity-graph/layout3d.test.ts · determinista en cualquier orden, dentro de la esfera unidad, el giro conserva distancias
entity-graph/Graph.tsx        · esferas con degradado, orden por profundidad, giro con arrastre y flechas, giro lento solo si se acepta movimiento (RF-282, RNF-61)
entity-graph/Graph.test.tsx   · las pruebas de RF-196 intactas, más teclado, sin controles y movimiento reducido
```

`layout.ts`, el círculo de la versión 1, se retira: lo sustituye `layout3d.ts`, que cumple lo mismo que él —pura y determinista— en tres dimensiones.

| Requisitos | RF-282, RF-283, RNF-61 |
|---|---|
| **Puerta** | Las pruebas del grafo de la versión 1 siguen en verde sin cambiarlas, y las propiedades de RF-283 pasan |
