import { describe, expect, it } from "vitest";

import schema from "../../../backend/openapi.json";

/**
 * RNF-38: las unicas escrituras son los encargos (spec §2.5). El cliente se
 * genera del esquema, asi que si el esquema no tiene otra ruta de escritura, el
 * frontend no puede tenerla. Cada ruta nueva que el backend anada o esta en
 * esta lista, o rompe la puerta y obliga a decidir si es un encargo.
 */
const ENCARGOS = new Set([
  "POST /interviews",
  "POST /interviews/{}/turns",
  "POST /novels",
  "POST /novels/{}/run",
  "POST /novels/{}/change-requests",
]);

function writes(): string[] {
  const out: string[] = [];
  for (const [path, operations] of Object.entries(schema.paths)) {
    for (const method of Object.keys(operations)) {
      if (method.toLowerCase() !== "get") out.push(`${method.toUpperCase()} ${path.replace(/\{[^}]+\}/g, "{}")}`);
    }
  }
  return out.sort();
}

describe("solo encargos escriben (RNF-38)", () => {
  it("toda operacion que no es de lectura en el esquema es un encargo", () => {
    const extra = writes().filter((w) => !ENCARGOS.has(w));
    expect(extra).toEqual([]);
  });

  it("hoy el esquema tiene exactamente los cinco encargos", () => {
    expect(writes()).toEqual([...ENCARGOS].sort());
  });
});
