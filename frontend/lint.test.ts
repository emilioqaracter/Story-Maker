// @vitest-environment node
import { ESLint } from "eslint";
import { describe, expect, it } from "vitest";

/**
 * Que las reglas de `eslint.config.js` pillan lo que dicen pillar. Una regla que
 * no salta sobre su propio ejemplo da confianza falsa, que es peor que no
 * tenerla (verification.md §4.7).
 */
const eslint = new ESLint();

async function messages(filePath: string, code: string): Promise<string[]> {
  const [result] = await eslint.lintText(code, { filePath });
  return (result?.messages ?? []).map((m) => `${m.ruleId}: ${m.message}`);
}

describe("reglas de frontend/ (VER-02)", () => {
  it("una funcionalidad no importa de otra (RNF-44)", async () => {
    const out = await messages("manuscript/x.tsx", 'import { Graph } from "../entity-graph/Graph";\nexport const g = Graph;\n');
    expect(out.some((m) => m.includes("Una funcionalidad no importa de otra"))).toBe(true);
  });

  it("commons/ no importa de ninguna funcionalidad, y nadie de la raiz", async () => {
    expect(
      (await messages("commons/x.ts", 'import { Debt } from "../narrative-debt/Debt";\nexport const d = Debt;\n')).some((m) =>
        m.includes("commons/ no importa"),
      ),
    ).toBe(true);
    expect(
      (await messages("manuscript/x.ts", 'import { routes } from "../routes";\nexport const r = routes;\n')).some((m) =>
        m.includes("raiz de composicion"),
      ),
    ).toBe(true);
  });

  it("la raiz de composicion y commons/ si se pueden importar", async () => {
    expect(await messages("manuscript/x.ts", 'import { api } from "../commons/api/client";\nexport const a = api;\n')).toEqual([]);
  });

  it("HTTP solo en commons/api/ (RI-55)", async () => {
    const out = await messages("manuscript/x.ts", 'export const f = () => fetch("/novels");\n');
    expect(out.some((m) => m.includes("RI-55"))).toBe(true);
  });

  it("ningun texto como HTML (RF-163)", async () => {
    const out = await messages("manuscript/x.tsx", "export const X = ({ t }: { t: string }) => <div dangerouslySetInnerHTML={{ __html: t }} />;\n");
    expect(out.some((m) => m.includes("RF-163"))).toBe(true);
  });

  it("el navegador guarda solo desde commons/storage/ (RD-29)", async () => {
    const out = await messages("manuscript/x.ts", 'export const f = () => localStorage.setItem("prosa", "...");\n');
    expect(out.some((m) => m.includes("RD-29"))).toBe(true);
  });

  it("ninguna dependencia fuera de la lista, ni direcciones externas (RNF-41, RI-56)", async () => {
    const out = await messages(
      "manuscript/x.ts",
      'import Anthropic from "@anthropic-ai/sdk";\nexport const a = Anthropic;\nexport const u = "https://api.example.com";\n',
    );
    expect(out.some((m) => m.includes("RNF-41"))).toBe(true);
    expect(out.some((m) => m.includes("RI-56"))).toBe(true);
  });
});
