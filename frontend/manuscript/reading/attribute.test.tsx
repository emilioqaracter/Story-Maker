import { render } from "@testing-library/react";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { attribute, attributeSelection, type SceneSpan } from "./attribute";
import { Scenes } from "./Chapter";

/** Escenas consecutivas de longitudes arbitrarias, como en la lectura. */
const spans = fc.array(fc.integer({ min: 1, max: 40 }), { minLength: 1, maxLength: 8 }).map((lengths) => {
  const out: SceneSpan[] = [];
  let start = 0;
  lengths.forEach((len, i) => {
    out.push({ id: `1.${i + 1}`, start, end: start + len });
    start += len;
  });
  return out;
});

describe("atribucion de una seleccion a una escena (RF-180)", () => {
  it("toda seleccion se atribuye a exactamente una escena, o a ninguna si cruza dos", () => {
    fc.assert(
      fc.property(
        spans.chain((s) => {
          const total = s.at(-1)?.end ?? 1;
          return fc.tuple(fc.constant(s), fc.integer({ min: 0, max: total }), fc.integer({ min: 0, max: total }));
        }),
        ([s, a, b]) => {
          const got = attribute(s, a, b);
          const lo = Math.min(a, b);
          const hi = Math.max(a, b);
          const inside = s.filter((span) => span.start <= lo && hi <= span.end);
          if (lo === hi) expect(got).toBeNull();
          else if (inside.length === 1) expect(got).toBe(inside[0]?.id);
          else expect(got).toBeNull();
        },
      ),
    );
  });

  it("sobre el DOM de la lectura dice lo mismo", () => {
    const { container } = render(
      <Scenes
        scenes={[
          { scene_id: "1.1", scene_number: 1, text: "Primera escena.", changed: false },
          { scene_id: "1.2", scene_number: 2, text: "Segunda escena.", changed: false },
        ]}
      />,
    );
    const [first, second] = [...container.querySelectorAll("[data-scene-id] p")];
    const select = (a: Node, ao: number, b: Node, bo: number) => {
      const selection = document.getSelection();
      if (!selection) throw new Error("sin seleccion");
      selection.removeAllRanges();
      selection.setBaseAndExtent(a, ao, b, bo);
      return attributeSelection(selection);
    };
    const t1 = first?.firstChild;
    const t2 = second?.firstChild;
    if (!t1 || !t2) throw new Error("sin texto");
    expect(select(t1, 0, t1, 7)).toBe("1.1");
    expect(select(t2, 2, t2, 9)).toBe("1.2");
    expect(select(t1, 3, t2, 4)).toBeNull();
    expect(select(t1, 3, t1, 3)).toBeNull();
  });
});
