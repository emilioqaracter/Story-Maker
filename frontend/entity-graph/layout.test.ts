import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { layout, SIZE } from "./layout";

const ids = fc.uniqueArray(fc.stringMatching(/^[a-z]{1,8}$/), { maxLength: 40 });

describe("posicion de los nodos (RNF-47)", () => {
  it("es determinista: el mismo canon dibuja el mismo grafo, venga en el orden que venga", () => {
    fc.assert(
      fc.property(ids.chain((xs) => fc.tuple(fc.constant(xs), fc.shuffledSubarray(xs, { minLength: xs.length }))), ([xs, shuffled]) => {
        expect([...layout(shuffled)].sort()).toEqual([...layout(xs)].sort());
      }),
    );
  });

  it("todo nodo cae dentro del dibujo y no hay dos en el mismo sitio", () => {
    fc.assert(
      fc.property(ids, (xs) => {
        const points = [...layout(xs).values()];
        expect(points).toHaveLength(xs.length);
        for (const p of points) {
          expect(p.x).toBeGreaterThanOrEqual(0);
          expect(p.x).toBeLessThanOrEqual(SIZE);
          expect(p.y).toBeGreaterThanOrEqual(0);
          expect(p.y).toBeLessThanOrEqual(SIZE);
        }
        expect(new Set(points.map((p) => `${p.x},${p.y}`)).size).toBe(points.length);
      }),
    );
  });
});
