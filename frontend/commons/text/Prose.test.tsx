import { render } from "@testing-library/react";
import fc from "fast-check";
import { describe, expect, it } from "vitest";

import { HOSTILE } from "../testing/fixtures";
import { paragraphs, Prose } from "./Prose";

describe("prosa como texto (RF-163, RNF-40)", () => {
  it("el marcado y los scripts se leen tal cual y no se ejecutan", () => {
    const { container } = render(<Prose text={HOSTILE} />);
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("b")).toBeNull();
    expect(container.textContent).toContain("<script>window.__pwned = true</script>");
    expect((globalThis as { __pwned?: boolean }).__pwned).toBeUndefined();
  });

  it("cada parrafo es exactamente el trozo del original en su desplazamiento", () => {
    const text = fc.array(fc.oneof(fc.string({ maxLength: 20 }), fc.constantFrom("\n", "\n\n", "\n \n", " ")), {
      maxLength: 25,
    });
    fc.assert(
      fc.property(text, (parts) => {
        const source = parts.join("");
        let last = -1;
        for (const p of paragraphs(source)) {
          expect(source.slice(p.offset, p.offset + p.text.length)).toBe(p.text);
          expect(p.offset).toBeGreaterThan(last);
          expect(p.text.length).toBeGreaterThan(0);
          last = p.offset;
        }
      }),
    );
  });
});
