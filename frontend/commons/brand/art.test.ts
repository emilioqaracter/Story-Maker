import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { ASPECTS, CATALOG, COVERS, coverFor, fnv1a, illustration, STYLE } from "./art";

describe("catalogo de ilustraciones (RF-275)", () => {
  it("es cerrado: identificadores unicos, con uso, aspecto admitido y descripcion", () => {
    const ids = CATALOG.map((i) => i.id);
    expect(new Set(ids).size).toBe(ids.length);
    for (const image of CATALOG) {
      expect(image.id).toMatch(/^[a-z]+(-[a-z]+)+$/);
      expect(image.use.length).toBeGreaterThan(0);
      expect(ASPECTS as readonly string[]).toContain(image.aspect);
      expect(image.prompt.length).toBeGreaterThan(40);
    }
  });

  it("el estilo comun prohibe texto, logos y personas reconocibles", () => {
    for (const banned of ["no text", "no letters", "no numbers", "no logos", "No recognizable real people"]) {
      expect(STYLE).toContain(banned);
    }
  });

  it("tiene las tres bandas y seis portadas verticales", () => {
    expect(COVERS).toHaveLength(6);
    for (const id of COVERS) expect(CATALOG.find((i) => i.id === id)?.aspect).toBe("2:3");
    for (const id of ["hero-estadio", "entrevista-banquillo", "estado-pista"]) expect(CATALOG.some((i) => i.id === id)).toBe(true);
  });

  it("una ilustracion que no existe se resuelve a undefined, no a un error (RF-277)", () => {
    expect(illustration("no-existe")).toBeUndefined();
  });
});

describe("portada por novela (RF-278)", () => {
  it("la misma novela da siempre la misma portada, y siempre una del catalogo", () => {
    fc.assert(
      fc.property(fc.string(), (id) => {
        const cover = coverFor(id);
        expect(COVERS).toContain(cover);
        expect(coverFor(id)).toBe(cover);
      }),
    );
  });

  it("FNV-1a da los valores de referencia", () => {
    expect(fnv1a("")).toBe(0x811c9dc5);
    expect(fnv1a("a")).toBe(0xe40c292c);
    expect(fnv1a("foobar")).toBe(0xbf9cf968);
  });
});
