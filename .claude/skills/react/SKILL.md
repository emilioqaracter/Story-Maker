---
name: react
description: "Escribir código de frontend de Story-Maker con React y TypeScript: componentes, cliente generado desde el OpenAPI, visualización del estado narrativo, grafo de entidades y curva de tensión. Úsala al crear o modificar cualquier pantalla, componente, hook o llamada a la API desde frontend/."
---

# Frontend · React

Cómo se escribe `frontend/` en este proyecto.

Antes de crear cualquier fichero, pasa por el proceso C de `AGENTS.md` §6.4.

## 1. Paquete por funcionalidad, no FSD

`frontend/` se organiza **por funcionalidad** (`architecture.md` §2.3). **No se usa Feature-Sliced Design**: nada de `app/`, `pages/`, `widgets/`, `features/`, `entities/` y `shared/` como capas.

```
frontend/
├── commons/         · cliente generado, tipos y componentes compartidos
├── manuscript/      · lectura de capítulos congelados
├── entity-graph/    · grafo de entidades con vigencia
├── tension-curve/   · curva de tensión de la obra
├── narrative-debt/  · setups abiertos sin payoff
└── run-health/      · métricas de salud de la tirada
```

Cada funcionalidad lleva dentro sus componentes, sus hooks, su estado local y sus tests. Dos reglas:

1. **Una funcionalidad no importa de otra.** Solo de `commons/`. Lo comprueba la regla de fronteras de `eslint` en CI (VER-02).
2. **A `commons/` se baja por uso, no por previsión**: cuando lo usan dos funcionalidades.

**El cliente generado vive en `commons/`, nunca duplicado por funcionalidad.** Es uno solo, sale del esquema OpenAPI, y tener dos copias rompe la garantía de VER-08 de que un cambio incompatible del backend rompa la compilación.

## 2. La regla que gobierna todo lo demás

**El frontend es un observador de solo lectura** (`architecture.md` §2.1). No aprueba, no corrige, no desbloquea, no escribe canon.

No es una limitación de alcance: cualquier interacción de la interfaz que condicione el ciclo de generación reintroduce la aprobación manual que prohíbe PRO-11, y lo hace por la puerta de atrás, sin regla de precedencia ni agente responsable.

De ahí sale una prueba que puedes aplicar a cualquier componente que escribas: **el sistema termina una novela con el frontend apagado**. Si lo que estás construyendo hace que eso deje de ser cierto, para y ejecuta el proceso B de `AGENTS.md` §6.3.

Consecuencias prácticas:

- Ningún botón «aprobar capítulo», «rechazar escena», «forzar regeneración» ni «continuar».
- Ningún formulario que escriba en el canon.
- El brief (PRO-01) sí entra desde aquí: es un encargo, ocurre antes del ciclo y no lo interrumpe.

## 3. El cliente no se escribe a mano

Se **genera** desde el esquema OpenAPI que produce FastAPI (`architecture.md` §2.2). Es el único punto de acoplamiento entre las dos mitades.

El objetivo es que un cambio incompatible del backend **rompa la compilación, no la pantalla** (VER-08). Un cliente escrito a mano convierte un error de contrato en un fallo silencioso en tiempo de ejecución, que es exactamente lo que este diseño intenta evitar.

`tsc --strict`, sin excepciones y sin `any` (VER-01).

## 4. Qué se muestra

| Vista | Fuente |
|---|---|
| Manuscrito | Solo capítulos congelados. Un borrador (PRO-06) no sale del backend |
| Grafo de entidades | Proyección del grafo, con relaciones tipadas y su vigencia |
| Curva de tensión | Proyección a lo largo de la obra |
| Deuda narrativa | Setups abiertos sin payoff |
| Salud de la tirada | Las métricas de `architecture.md` §11 |

Todo son **proyecciones derivadas**. El frontend nunca recibe el registro de eventos en crudo.

## 5. Representación gráfica

El grafo de entidades y la curva de tensión no se leen bien en una tabla, así que necesitan dibujarse. **Con qué librería es una decisión abierta** (`architecture.md` §2.2): no está fijada.

No la fijes de facto metiendo una dependencia sin pasar por el proceso B. Si necesitas dibujar antes de que se decida, hazlo con SVG a mano y déjalo dicho.

## 6. Tests

- `vitest` y React Testing Library (VER-05).
- Los tests van contra el cliente generado, con el backend doblado. Si un test necesita un backend real, es un test de contrato y le toca `schemathesis` en el otro lado.
- `eslint` para el análisis estático (VER-02).

## 7. Lo que no se hace aquí

- No se replica lógica de dominio del backend. Si el frontend necesita calcular algo sobre el canon, la proyección la calcula el backend y la sirve.
- No se guarda estado del canon en el cliente. Lo que se cachea son respuestas, y se invalidan al congelar un capítulo.
- No se añade una ruta que escriba. Si parece que hace falta, es el proceso B de `AGENTS.md` §6.3, no un `POST` nuevo.
