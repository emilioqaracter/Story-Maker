---
name: fastapi
description: "Escribir código de backend de Story-Maker con Python y FastAPI: endpoints, modelos pydantic, esquema OpenAPI, validación de la salida de los agentes, guardrails de tokens y estructura de backend/. Úsala al crear o modificar cualquier ruta, DTO, dependencia o servicio del backend, y al decidir cómo entra en el sistema el texto que devuelve un modelo."
---

# Backend · Python y FastAPI

Cómo se escribe `backend/` en este proyecto. Las reglas salen de `docs/architecture.md` y `docs/verification.md`; esta skill las junta en un solo sitio.

Antes de crear cualquier fichero, pasa por el proceso C de `AGENTS.md` §6.4: aquí está el **cómo**, allí está el **si procede**.

## 1. Paquete por funcionalidad

`backend/` se organiza **por funcionalidad, no por capa técnica** (`architecture.md` §2.3). Nada de un `models/`, un `services/` y un `routers/` transversales.

```
backend/
├── commons/         · lo que usan dos o más funcionalidades
├── orchestration/   · agente 0, raíz de composición
├── planning/        · agentes 1 y 2
├── context/         · agente 3
├── generation/      · agentes 4 y 5
├── verification/    · agentes 6, 7, 8 y 9
├── canon/           · agentes 10 y 11, más los cinco almacenes
└── supervision/     · agente 12
```

Cada funcionalidad lleva dentro sus modelos pydantic, su lógica, sus rutas, su esquema y sus tests. Tres reglas:

1. **Una funcionalidad no importa de otra.** Solo de `commons/`.
2. **Dos excepciones, una en cada extremo**: `orchestration/` conoce a todas y ninguna lo conoce a él; de `canon/` importan todas en lectura (skills `canon.*` y proyecciones) y él no importa de ninguna. Tres pisos: `canon/` abajo, funcionalidades en medio, `orchestration/` arriba.
3. **A `commons/` se baja por uso, no por previsión**: cuando lo usan dos funcionalidades, nunca cuando parece que podría hacer falta.

Las reglas 1 y 2 las comprueba `import-linter` en la puerta de CI (VER-02). No son convención: sin esa comprobación, el paquete por funcionalidad se convierte en capas técnicas con otro nombre en veinte ficheros.

## 2. El OpenAPI es el contrato, no un subproducto

El esquema que FastAPI genera es la fuente de verdad de la frontera entre `backend/` y `frontend/` (`architecture.md` §2.2). De ahí se sigue:

- Todo endpoint declara sus modelos de entrada y salida. Nunca `dict` ni `Any` en una firma pública.
- El cliente TypeScript del frontend **se genera** desde ese esquema. Un cambio incompatible debe romper la compilación del frontend, no la pantalla (VER-08).
- Cambiar la forma de una respuesta es cambiar el contrato: pasa por el proceso B de `AGENTS.md` §6.3 antes de tocar el código.

## 3. La frontera de confianza está en el parseo

La salida de un modelo entra como texto. **El punto donde ese texto se convierte en objeto tipado es la frontera de confianza del sistema entero** (VER-01).

- Toda respuesta de agente se valida contra su modelo pydantic antes de tocar nada. Si no valida, se rechaza; no se parsea a mano ni se repara con expresiones regulares.
- Los artefactos tienen forma declarada: `scene.spec`, el delta canónico (CAN-11, salida de `delta.extract`) y las puntuaciones de `*.audit`. Se nombran por la skill que los produce o por su ID (`architecture.md` §6.2). Un campo nuevo es un cambio de contrato.
- **Ninguna cadena procedente de un modelo alcanza el sistema de ficheros, la red o la base de datos sin pasar antes por un validador de esquema** (VER-02). Es la regla que evita la familia entera de ataques de `verification.md` §5.9.

## 4. Guardrails antes de llamar, no después

`verification.md` §5.4 los define; en FastAPI viven como dependencias, no como comprobaciones sueltas dentro de cada handler:

| Guardrail | Dónde |
|---|---|
| Esquema de salida | Modelo pydantic de respuesta del agente |
| Skills permitidas por agente | Lista declarada; una llamada fuera de lista se rechaza y se traza |
| Techo de tokens | Entrada ≤70.000, entrada más salida ≤85.000, **comprobado antes de la llamada** |
| Canon de solo lectura | Solo el Archivero abre la conexión en escritura |
| Puerto de proveedor | Ninguna llamada a un SDK de proveedor fuera de `commons/` |

Ese techo es del sistema al redactar la novela. No limita el código, limita lo que el código puede mandar a un modelo.

## 4.1 Proveedores y contador de tokens

Los dos proveedores están fijados en `architecture.md` §4.8: **Claude** para los once agentes de modelo, **OpenRouter** para los embeddings del índice de prosa.

- **Nadie importa el SDK de un proveedor fuera del puerto de `commons/`**, que expone `complete` y `embed`. Un agente que importe el SDK ata once ficheros a un proveedor y convierte un cambio de modelo, que `verification.md` §5.8 trata como un despliegue, en una refactorización.
- **Hay un solo contador de tokens**, en `commons/`: `tiktoken` local con codificación fija como estimador, y el bloque `usage` de cada respuesta como fuente de verdad. Lo usan el empaquetado, la admisión, las herramientas y el guardarraíl. Dos contadores distintos dejan CTX-I1 sin forma de comprobarse.
- **`tiktoken` nunca se usa crudo.** Es el tokenizador de OpenAI e infracuenta a Claude entre un 15 y un 20 % en prosa inglesa, y más en español. Todo lo que devuelve se multiplica por el factor de seguridad de `architecture.md` §4.8 y se redondea hacia arriba antes de compararlo con cualquier techo.
- **Un factor por modelo.** Los tokenizadores de Claude difieren hasta un 30 % entre generaciones; un factor calibrado contra un modelo no vale para otro. Sin factor conocido, la llamada no se admite.
- **El recuento real que devuelve el proveedor se traza siempre**, emparejado con el estimado. La entrada real es la suma de los tres campos de `usage`. Que el estimado nunca se quede corto es una propiedad de `hypothesis`, no una confianza.

## 5. Agentes que son código

El Orquestador y el Documentalista no son llamadas a modelo: son módulos de Python (`architecture.md` §6). Su contrato vincula igual. Un Documentalista que devuelve un paquete fuera de presupuesto rompe la restricción de contexto antes de que ningún modelo llegue a verla, así que esa comprobación es un test, no un comentario.

## 6. Tipos y análisis estático

- `mypy --strict` o `pyright` en todo `backend/` (VER-01).
- `ruff` y `bandit` para el análisis estático, `pip-audit` para dependencias (VER-02).
- Las funciones puras y pequeñas del calendario, la clasificación y el empaquetador de contexto son las candidatas de `CrossHair` y `z3` (VER-03). Escríbelas puras a propósito: es lo que las hace verificables.

## 7. Tests

- `pytest` con el `TestClient` de FastAPI (VER-05).
- `hypothesis` para los invariantes que ya están escritos como propiedades universales en `definitions.md` (VER-06). Traducirlos es mecánico: «el recálculo de la clasificación es invariante a la permutación de los encuentros», «el paquete nunca supera 70.000 tokens de entrada».
- **Todo test que involucre un agente usa un doble determinista.** Uno que llama a un modelo real no es un test, es un eval.
- Los verificadores deterministas son el módulo con cobertura de mutación (VER-07): son la red de seguridad del sistema, y un verificador con tests que no detectan su ruptura es peor que no tenerlo.

## 8. Lo que no se hace aquí

- No se escribe canon fuera del Archivero.
- No se añade una segunda capa de observabilidad: VER-09 está adjudicado a Langfuse.
- No se crea una carpeta `api/`. Las rutas viven en su funcionalidad y la aplicación se compone en `orchestration/` (`architecture.md` §2.3).
- No se inventan umbrales. Salen de los documentos, o se declaran como propuesta explicando su origen.
