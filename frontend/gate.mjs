#!/usr/bin/env node
// La puerta del frontend: todas las comprobaciones que un cambio tiene que
// pasar, en un solo comando, como backend/gate.py. Mientras la puerta sea una
// lista de comandos a mano, «la puerta pasa» significa «paso cuando la ejecute
// alguien» (spec §7.2, verification.md §5.7).
//
//     node gate.mjs          # lo que corre en cada cambio
//     node gate.mjs --full   # anade la auditoria de dependencias

import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));
const SCHEMA_JSON = path.resolve(ROOT, "..", "backend", "openapi.json");
const CLIENT = path.join(ROOT, "commons", "api", "schema.d.ts");
/** Una ruta que la lectura usa: quitarla del esquema tiene que romper la compilacion (RNF-43). */
const USED_ROUTE = "/novels/{novel_id}/versions/{version}/chapters/{number}";

function run(command, args) {
  return spawnSync(command, args, { cwd: ROOT, encoding: "utf-8", shell: process.platform === "win32" });
}

function npx(...args) {
  return run("npx", ["--no-install", ...args]);
}

const normalize = (text) => text.replace(/\r\n/g, "\n");

function generate(schemaPath) {
  const dir = mkdtempSync(path.join(tmpdir(), "story-maker-client-"));
  const out = path.join(dir, "schema.d.ts");
  const result = npx("openapi-typescript", schemaPath, "-o", out, "--default-non-nullable", "false");
  const text = result.status === 0 ? readFileSync(out, "utf-8") : null;
  return { dir, text, result };
}

/** RNF-45: regenerar el cliente desde el esquema versionado no produce diferencias. */
function clientUpToDate() {
  const { dir, text, result } = generate(SCHEMA_JSON);
  try {
    if (text === null) return { ok: false, output: result.stdout + result.stderr };
    const same = normalize(text) === normalize(readFileSync(CLIENT, "utf-8"));
    return { ok: same, output: same ? "" : "commons/api/schema.d.ts no coincide con backend/openapi.json: npm run gen\n" };
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

/** RNF-43, VER-08: con una ruta usada fuera del esquema, `tsc` tiene que fallar. */
function contractBreaks() {
  const schema = JSON.parse(readFileSync(SCHEMA_JSON, "utf-8"));
  if (!(USED_ROUTE in schema.paths)) return { ok: false, output: `El esquema ya no tiene ${USED_ROUTE}\n` };
  delete schema.paths[USED_ROUTE];
  const dir = mkdtempSync(path.join(tmpdir(), "story-maker-contract-"));
  const mutated = path.join(dir, "openapi.json");
  writeFileSync(mutated, JSON.stringify(schema));
  const original = readFileSync(CLIENT, "utf-8");
  try {
    const { dir: genDir, text } = generate(mutated);
    rmSync(genDir, { recursive: true, force: true });
    if (text === null) return { ok: false, output: "No se pudo generar el cliente mutado\n" };
    writeFileSync(CLIENT, text);
    const result = npx("tsc", "--noEmit");
    const broke = result.status !== 0 && result.stdout.includes(USED_ROUTE);
    return {
      ok: broke,
      output: broke ? "" : `Quitar ${USED_ROUTE} del esquema no rompio la compilacion\n${result.stdout}`,
    };
  } finally {
    writeFileSync(CLIENT, original);
    rmSync(dir, { recursive: true, force: true });
  }
}

function command(...args) {
  return () => {
    const result = npx(...args);
    return { ok: result.status === 0, output: result.stdout + result.stderr };
  };
}

const CHECKS = [
  { name: "cliente al dia", what: "El cliente generado es el del esquema versionado (RI-54, RNF-45)", check: clientUpToDate },
  { name: "tipos", what: "tsc --strict sin any: las piezas encajan antes de ejecutar nada (VER-01)", check: command("tsc", "--noEmit") },
  { name: "fronteras y seguridad", what: "eslint: fronteras de architecture.md §2.3, texto como dato, HTTP solo en commons/api/ (VER-02)", check: command("eslint", ".") },
  { name: "pruebas y propiedades", what: "vitest contra dobles del mismo esquema, con fast-check (VER-05, VER-06)", check: command("vitest", "run") },
  { name: "contrato que se rompe", what: "Quitar una ruta usada del esquema rompe la compilacion (VER-08)", check: contractBreaks },
  { name: "vulnerabilidades en dependencias", what: "npm audit (RNF-41)", check: () => {
    const result = run("npm", ["audit", "--audit-level=high"]);
    return { ok: result.status === 0, output: result.stdout + result.stderr };
  }, slow: true },
];

const full = process.argv.includes("--full");
let failed = 0;
for (const c of CHECKS) {
  if (c.slow && !full) continue;
  const start = Date.now();
  const { ok, output } = c.check();
  const seconds = ((Date.now() - start) / 1000).toFixed(1);
  process.stdout.write(`${ok ? "  ok  " : "  FALLA"} ${c.name} (${seconds}s) · ${c.what}\n`);
  if (!ok) {
    failed += 1;
    process.stdout.write(output);
  }
}
process.stdout.write(failed ? `\npuerta: ${failed} comprobaciones fallan\n` : "\npuerta: en verde\n");
process.exit(failed ? 1 : 0);
