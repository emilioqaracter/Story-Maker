import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { chapterAt } from "../../commons/testing/fixtures";
import { broken, changedChapters } from "./marks";

describe("marcas de cambio (RF-184 a RF-186)", () => {
  it("un capitulo sin marca de cambiado tiene el mismo texto en dos versiones del doble", () => {
    for (const n of [1, 2]) {
      expect(broken(chapterAt(1, n).scenes, chapterAt(2, n).scenes)).toEqual([]);
    }
  });

  it("la comprobacion detecta una escena sin marca cuyo texto cambio", () => {
    fc.assert(
      fc.property(
        fc.uniqueArray(fc.stringMatching(/^[a-z][a-z0-9]{0,5}$/), { minLength: 1, maxLength: 8 }),
        fc.array(fc.boolean(), { minLength: 8, maxLength: 8 }),
        fc.array(fc.boolean(), { minLength: 8, maxLength: 8 }),
        (ids, rewritten, marked) => {
          const before = ids.map((id) => ({ scene_id: id, text: `texto de ${id}`, changed: false }));
          const after = ids.map((id, i) => ({
            scene_id: id,
            text: rewritten[i] ? `otro texto de ${id}` : `texto de ${id}`,
            changed: marked[i] === true,
          }));
          const expected = ids.filter((_, i) => rewritten[i] && !marked[i]);
          expect(broken(before, after)).toEqual(expected);
        },
      ),
    );
  });

  it("resume los capitulos cambiados del manifiesto", () => {
    expect(changedChapters([{ number: 1, changed: true }, { number: 2, changed: false }])).toEqual([1]);
  });
});
