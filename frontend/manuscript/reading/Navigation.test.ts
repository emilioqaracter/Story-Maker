import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { neighbours } from "./Navigation";

describe("anterior y siguiente (RF-181)", () => {
  it("son el congelado inmediatamente antes y despues, sin saltar ninguno", () => {
    fc.assert(
      fc.property(fc.uniqueArray(fc.integer({ min: 1, max: 60 }), { maxLength: 20 }), fc.integer({ min: 1, max: 60 }), (chapters, current) => {
        const { previous, next } = neighbours(chapters, current);
        const before = chapters.filter((n) => n < current);
        const after = chapters.filter((n) => n > current);
        expect(previous).toBe(before.length ? Math.max(...before) : undefined);
        expect(next).toBe(after.length ? Math.min(...after) : undefined);
      }),
    );
  });
});
