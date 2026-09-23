import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { cacheKey, changed, invalidate, ResponseCache } from "./cache";

const novel = fc.stringMatching(/^[a-z0-9][a-z0-9-]{2,12}$/);
const entry = fc.tuple(novel, fc.integer({ min: 1, max: 4 }), fc.string({ maxLength: 12 }), fc.integer());

describe("cache por novela y version (RD-28)", () => {
  it("invalidar una novela suelta solo las suyas y deja intactas las demas", () => {
    fc.assert(
      fc.property(fc.array(entry, { maxLength: 30 }), novel, (entries, target) => {
        const map = new Map(entries.map(([n, v, r, value]) => [cacheKey(n, v, r), value]));
        const out = invalidate(map, target);
        for (const [n, v, r] of entries) {
          const key = cacheKey(n, v, r);
          if (n === target) expect(out.has(key)).toBe(false);
          else expect(out.get(key)).toBe(map.get(key));
        }
      }),
    );
  });

  it("el mismo estado no invalida; un capitulo congelado mas o un cambio de cierre si", () => {
    fc.assert(
      fc.property(fc.nat(50), fc.constantFrom(true, false, null), (frozen, closed) => {
        const s = { frozenChapters: frozen, closed };
        expect(changed(undefined, s)).toBe(false);
        expect(changed(s, { ...s })).toBe(false);
        expect(changed(s, { ...s, frozenChapters: frozen + 1 })).toBe(true);
        expect(changed(s, { ...s, closed: closed === true ? false : true })).toBe(true);
      }),
    );
  });

  it("observar el estado de una novela no toca la cache de otra", () => {
    const cache = new ResponseCache();
    cache.set(cacheKey("una-novela", 1, "chapters"), "a");
    cache.set(cacheKey("otra-novela", 1, "chapters"), "b");
    cache.observe("una-novela", { frozenChapters: 1, closed: null });
    cache.observe("una-novela", { frozenChapters: 2, closed: null });
    expect(cache.get(cacheKey("una-novela", 1, "chapters"))).toBeUndefined();
    expect(cache.get(cacheKey("otra-novela", 1, "chapters"))).toBe("b");
  });
});
