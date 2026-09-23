import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { quoteBetween } from "./anchor";

describe("la cita del ancla (RD-30, spec §7.3)", () => {
  it("es exactamente la subcadena seleccionada del texto de su escena, sin recortar ni normalizar", () => {
    fc.assert(
      fc.property(
        fc.string({ maxLength: 80 }).chain((text) =>
          fc.tuple(fc.constant(text), fc.integer({ min: 0, max: text.length }), fc.integer({ min: 0, max: text.length })),
        ),
        ([text, a, b]) => {
          const quote = quoteBetween(text, a, b);
          expect(quote).toBe(text.slice(Math.min(a, b), Math.max(a, b)));
          expect(text.includes(quote)).toBe(true);
        },
      ),
    );
  });

  it("conserva espacios y saltos de parrafo tal cual", () => {
    expect(quoteBetween("uno  dos\n\ntres", 3, 12)).toBe("  dos\n\ntr");
  });
});
