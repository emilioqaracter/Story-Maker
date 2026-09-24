import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { layout3d, project, rotate } from "./layout3d";

const ids = fc.uniqueArray(fc.stringMatching(/^[a-z]{1,6}$/), { maxLength: 24 });

function withEdges() {
  return ids.chain((list) =>
    fc.tuple(
      fc.constant(list),
      fc.array(fc.tuple(fc.constantFrom(...(list.length ? list : ["x"])), fc.constantFrom(...(list.length ? list : ["x"]))), {
        maxLength: 30,
      }),
    ),
  );
}

describe("posicion 3D del grafo (RF-283)", () => {
  it("es determinista: el mismo canon da la misma figura, se pida en el orden que se pida", () => {
    fc.assert(
      fc.property(withEdges(), ([list, edges]) => {
        const a = layout3d(list, edges);
        const b = layout3d([...list].reverse(), [...edges].reverse());
        expect([...a.entries()].sort()).toEqual([...b.entries()].sort());
      }),
      { numRuns: 40 },
    );
  });

  it("toda posicion es finita y cae dentro de la esfera unidad, y hay una por entidad", () => {
    fc.assert(
      fc.property(withEdges(), ([list, edges]) => {
        const out = layout3d(list, edges);
        expect(out.size).toBe(list.length);
        for (const p of out.values()) {
          expect(Number.isFinite(p.x) && Number.isFinite(p.y) && Number.isFinite(p.z)).toBe(true);
          expect(Math.hypot(p.x, p.y, p.z)).toBeLessThanOrEqual(1.0002);
        }
      }),
      { numRuns: 40 },
    );
  });

  it("una entidad sola queda en el centro, y dos relacionadas quedan mas cerca que dos sueltas", () => {
    expect(layout3d(["a"], [])).toEqual(new Map([["a", { x: 0, y: 0, z: 0 }]]));
    const many = ["a", "b", "c", "d", "e", "f"];
    const out = layout3d(many, [["a", "b"]]);
    const d = (u: string, v: string) => {
      const p = out.get(u);
      const q = out.get(v);
      return p && q ? Math.hypot(p.x - q.x, p.y - q.y, p.z - q.z) : NaN;
    };
    expect(d("a", "b")).toBeLessThan(d("c", "d"));
  });

  it("girar conserva la distancia al centro, y la proyeccion agranda lo de delante", () => {
    fc.assert(
      fc.property(fc.double({ min: -1, max: 1, noNaN: true }), fc.double({ min: -3, max: 3, noNaN: true }), (z, yaw) => {
        const p = { x: 0.3, y: -0.2, z: z * 0.5 };
        const r = rotate(p, yaw, yaw / 2);
        expect(Math.hypot(r.x, r.y, r.z)).toBeCloseTo(Math.hypot(p.x, p.y, p.z), 9);
      }),
    );
    const front = project({ x: 0.5, y: 0, z: 0.8 }, 480, 150);
    const back = project({ x: 0.5, y: 0, z: -0.8 }, 480, 150);
    expect(front.scale).toBeGreaterThan(1);
    expect(back.scale).toBeLessThan(1);
    expect(front.x).toBeGreaterThan(back.x);
    expect(project({ x: 0, y: 0, z: 0 }, 480, 150)).toEqual({ x: 240, y: 240, scale: 1, depth: 0 });
  });
});
