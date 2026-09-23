import createClient from "openapi-fetch";

import type { components, paths } from "./schema";

/**
 * El unico punto de acceso HTTP del frontend (RF-162, RI-55).
 *
 * Sus tipos salen de `schema.d.ts`, que se genera desde `backend/openapi.json`
 * (RI-54): si una ruta que se usa cambia de forma, esto deja de compilar.
 * El backend esta en el mismo origen (RI-56, D-67), asi que no hay direccion
 * que configurar. `fetch` se resuelve en cada llamada y no al crear el cliente:
 * lo que haya en `globalThis.fetch` en ese momento es lo que se usa.
 */
export const api = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? "",
  fetch: (request) => globalThis.fetch(request),
});

/** Los tipos de datos de la API. Ninguna funcionalidad declara los suyos (RD-31). */
export type Schemas = components["schemas"];
