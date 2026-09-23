// Reglas propias de frontend/. Ninguna herramienta las trae de serie
// (verification.md §4.2): sin ellas, el paquete por funcionalidad se vuelve
// capas tecnicas con otro nombre al cabo de veinte ficheros.

import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.dirname(fileURLToPath(import.meta.url));

/** El esquema del backend es lo unico de fuera de frontend/ que se puede leer: de el sale el contrato. */
const SCHEMA = path.resolve(ROOT, "..", "backend", "openapi.json");

/** Dependencias de la aplicacion. Ningun SDK de proveedor de modelo (RNF-41). */
export const RUNTIME = new Set(["react", "react-dom", "react-router", "openapi-fetch"]);
/** Ademas, en pruebas. */
export const TESTING = new Set([
  "vitest",
  "msw",
  "fast-check",
  "@testing-library/react",
  "@testing-library/dom",
  "eslint",
]);
/** Ademas, en la configuracion de las herramientas. */
export const TOOLING = new Set([
  "vite",
  "vitest",
  "@vitejs/plugin-react",
  "@eslint/js",
  "typescript-eslint",
  "eslint-plugin-react-hooks",
]);

const TOOLING_FILES = new Set(["vite.config.ts", "eslint.config.js", "eslint.rules.js", "gate.mjs"]);

function posix(p) {
  return p.split(path.sep).join("/");
}

/** `root` para la raiz de composicion; si no, la carpeta de primer nivel: la funcionalidad. */
export function areaOf(file) {
  const rel = posix(path.relative(ROOT, file));
  if (rel.startsWith("..")) return "outside";
  return rel.includes("/") ? rel.split("/")[0] : "root";
}

function kindOf(file) {
  const rel = posix(path.relative(ROOT, file));
  if (TOOLING_FILES.has(rel)) return "tooling";
  if (/\.test\.tsx?$/.test(rel) || rel.startsWith("commons/testing/")) return "testing";
  return "app";
}

function packageOf(source) {
  const parts = source.split("/");
  return source.startsWith("@") ? parts.slice(0, 2).join("/") : parts[0];
}

/**
 * architecture.md §2.3, las tres reglas, para frontend/:
 * una funcionalidad importa solo de si misma y de `commons/`; `commons/` no importa
 * de ninguna; la raiz de composicion (`main.tsx`, `routes.tsx`) importa de todas y
 * nadie importa de ella. Mas la lista cerrada de dependencias de RNF-41.
 */
export const boundaries = {
  meta: {
    type: "problem",
    docs: { description: "Fronteras entre funcionalidades y dependencias permitidas" },
    schema: [],
  },
  create(context) {
    const file = context.filename;
    const from = areaOf(file);
    const kind = kindOf(file);

    function check(node) {
      if (!node.source || typeof node.source.value !== "string") return;
      const source = node.source.value;

      if (source.startsWith(".")) {
        const target = path.resolve(path.dirname(file), source);
        const to = areaOf(target);
        if (to === "outside") {
          if (target !== SCHEMA) {
            context.report({ node, message: `Fuera de frontend/ solo se lee backend/openapi.json: ${source}` });
          }
          return;
        }
        if (to === "root" && from !== "root") {
          context.report({ node, message: "Nadie importa de la raiz de composicion" });
          return;
        }
        if (from === "root" || from === to || to === "commons") return;
        context.report({
          node,
          message:
            from === "commons"
              ? `commons/ no importa de ninguna funcionalidad: ${to}/`
              : `Una funcionalidad no importa de otra: ${from}/ -> ${to}/. Solo de commons/`,
        });
        return;
      }

      if (source.startsWith("node:")) {
        if (kind !== "tooling") context.report({ node, message: `Modulo de Node fuera de la configuracion: ${source}` });
        return;
      }
      const pkg = packageOf(source);
      const allowed =
        RUNTIME.has(pkg) ||
        (kind === "testing" && TESTING.has(pkg)) ||
        (kind === "tooling" && TOOLING.has(pkg));
      if (!allowed) {
        context.report({ node, message: `Dependencia no permitida en ${kind}: ${pkg} (RNF-41)` });
      }
    }

    return {
      ImportDeclaration: check,
      ImportExpression: check,
      ExportNamedDeclaration: check,
      ExportAllDeclaration: check,
    };
  },
};
