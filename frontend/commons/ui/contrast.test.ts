import { describe, expect, it } from "vitest";

import tokens from "../brand/tokens.css?raw";
import style from "../shell/style.css?raw";

/*
  El sistema visual como dato: los tokens semanticos de commons/shell/style.css,
  resueltos hasta los hexadecimales de la marca, cumplen el contraste AA en los
  dos temas. Si alguien cambia un token y rompe un par, falla aqui y no en la
  pantalla de quien lee.
*/

const stripComments = (css: string) => css.replace(/\/\*[\s\S]*?\*\//g, "");

/** Las declaraciones `--x: valor;` de cada bloque `:root { ... }`, en orden. */
function rootBlocks(css: string): Map<string, string>[] {
  return [...stripComments(css).matchAll(/:root\s*\{([^}]*)\}/g)].map(
    (m) => new Map([...(m[1] ?? "").matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)].map((d) => [d[1] ?? "", (d[2] ?? "").trim()])),
  );
}

const brand = rootBlocks(tokens).reduce((all, block) => new Map([...all, ...block]), new Map<string, string>());
const [lightBlock, darkBlock] = rootBlocks(style);
const light = new Map([...brand, ...(lightBlock ?? [])]);
const dark = new Map([...light, ...(darkBlock ?? [])]);
const THEMES = { claro: light, oscuro: dark } as const;

/** Un token hasta su hexadecimal. Falla cerrado: un token que no resuelve a un color es un error, no un pase. */
function hex(vars: Map<string, string>, name: string): string {
  const value = vars.get(name);
  if (value === undefined) throw new Error(`${name} no esta definido`);
  const ref = /^var\((--[\w-]+)\)$/.exec(value);
  if (ref) return hex(vars, ref[1] ?? "");
  if (/^#[0-9a-f]{6}$/i.test(value)) return value.toLowerCase();
  throw new Error(`${name} no resuelve a un hexadecimal: ${value}`);
}

function luminance(color: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const c = parseInt(color.slice(i, i + 2), 16) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * (r ?? 0) + 0.7152 * (g ?? 0) + 0.0722 * (b ?? 0);
}

/** WCAG 2.x. Pura. */
function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return ((hi ?? 0) + 0.05) / ((lo ?? 0) + 0.05);
}

/** Texto sobre fondo: 4.5:1 (WCAG 1.4.3). */
const TEXT: [string, string][] = [
  ["--heading", "--bg"],
  ["--text", "--bg"],
  ["--muted", "--bg"],
  ["--link", "--bg"],
  ["--heading", "--surface"],
  ["--text", "--surface"],
  ["--muted", "--surface"],
  ["--heading", "--field"],
  ["--primary-text", "--primary-bg"],
  ["--header-text", "--header-bg"],
  ["--sheet-ink", "--sheet-bg"],
  ["--sheet-muted", "--sheet-bg"],
  ["--sheet-ink", "--sheet-paper"],
  ["--sheet-muted", "--sheet-paper"],
];

/** Bordes de control, foco y formas de estado: 3:1 (WCAG 1.4.11 y 2.4.7). */
const GRAPHIC: [string, string][] = [
  ["--focus", "--bg"],
  ["--focus", "--surface"],
  ["--header-text", "--header-bg"],
  ["--sheet-ink", "--sheet-bg"],
  ["--control-line", "--bg"],
  ["--control-line", "--surface"],
  ["--control-line", "--field"],
  // El anillo del fallo va sobre el fondo (avisos y solicitudes), y el subrayado de la vista actual sobre la cabecera.
  ["--accent", "--bg"],
  ["--accent", "--header-bg"],
  // El circulo lleno de «aplicada» va sobre el fondo de su tarjeta.
  ["--ok", "--bg"],
];

describe("tokens del sistema visual (BRAND.md §1)", () => {
  for (const [theme, vars] of Object.entries(THEMES)) {
    it.each(TEXT)(`tema ${theme}: el texto %s sobre %s llega a 4.5:1`, (fg, bg) => {
      expect(contrast(hex(vars, fg), hex(vars, bg))).toBeGreaterThanOrEqual(4.5);
    });
    it.each(GRAPHIC)(`tema ${theme}: la forma %s sobre %s llega a 3:1`, (fg, bg) => {
      expect(contrast(hex(vars, fg), hex(vars, bg))).toBeGreaterThanOrEqual(3);
    });
  }

  it("la cabecera es azul de titulares en los dos temas: el logo es negativo y en claro desaparece", () => {
    expect(hex(light, "--header-bg")).toBe("#1e2d3d");
    expect(hex(dark, "--header-bg")).toBe("#1e2d3d");
  });

  it("la hoja del capitulo es papel y tinta en los dos temas", () => {
    for (const vars of [light, dark]) {
      expect(hex(vars, "--sheet-bg")).toBe(hex(brand, "--color-papel-alto"));
      expect(hex(vars, "--sheet-ink")).toBe(hex(brand, "--color-tinta"));
    }
  });

  it("la interfaz no escribe colores propios ni redefine los de la marca", () => {
    const own = stripComments(style);
    expect(own.match(/#[0-9a-f]{3,8}\b/gi) ?? []).toEqual([]);
    const declared = [...(lightBlock?.keys() ?? []), ...(darkBlock?.keys() ?? [])];
    expect(declared.filter((k) => /^--(marca|color|font)-(?!ui$)/.test(k))).toEqual([]);
  });

  it("el verde es solo el del exito: un unico uso, el de «aplicada»", () => {
    const uses = stripComments(style).match(/var\(--ok\)/g) ?? [];
    expect(uses).toHaveLength(1);
    expect(stripComments(style).match(/var\(--color-verde\)/g)).toHaveLength(1);
  });
});

describe("foco y movimiento", () => {
  const css = stripComments(style);

  it("todo lo que recibe foco lo muestra, con un trazo de 3 px del token de foco", () => {
    expect(css).toMatch(/:focus-visible\s*\{\s*outline:\s*3px solid var\(--focus\)/);
  });

  it("ningun selector quita el contorno del foco visible", () => {
    const rules = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)];
    const offenders = rules
      .filter((r) => /outline:\s*(none|0)\b/.test(r[2] ?? ""))
      .map((r) => (r[1] ?? "").trim())
      .filter((selector) => !selector.includes(":not(:focus-visible)"));
    expect(offenders).toEqual([]);
  });

  it("con prefers-reduced-motion no hay animaciones ni transiciones", () => {
    const block = /@media \(prefers-reduced-motion: reduce\)\s*\{([\s\S]*?)\n\}/.exec(css)?.[1] ?? "";
    expect(block).toMatch(/animation:\s*none !important/);
    expect(block).toMatch(/transition:\s*none !important/);
  });

  it("nada dura mas de 400 ms salvo el indicador de carga, que gira sin parpadear (BRAND.md §4)", () => {
    const durations = [...css.matchAll(/(\d+)ms/g)].map((m) => Number(m[1]));
    expect(durations.filter((d) => d > 400)).toEqual([900]);
    expect(css).toMatch(/animation:\s*gira 900ms linear infinite/);
  });
});
