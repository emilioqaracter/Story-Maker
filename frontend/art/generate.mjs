#!/usr/bin/env node
/* eslint-disable local/boundaries -- Guion de desarrollo, no aplicacion: escribe ficheros con los modulos de Node y
   llama a Google AI Studio. La lista cerrada de RNF-41 es la de la aplicacion y sus pruebas; este fichero no lo
   importa nadie ni lo monta ninguna ruta (architecture.md §2.3, art/; srs-frontend-v2.md RNF-59). */
/* global fetch, setTimeout, Buffer -- los de Node, que la configuracion de eslint no declara para .mjs */
// Genera las ilustraciones deportivas del catalogo con Google AI Studio
// (`specs/srs-frontend-v2.md` RF-275, RF-276, D-115, D-120; tramo T55).
//
// La clave es de quien ejecuta el guion y nunca entra en el repositorio: se lee
// de la variable GEMINI_API_KEY o de `art/.env.local`, que git ignora, y viaja
// solo en la cabecera `x-goog-api-key`. El guion no la imprime nunca.
//
//     node art/generate.mjs                    # genera las que faltan
//     node art/generate.mjs --force            # las regenera todas
//     node art/generate.mjs --only portada-tenis,hero-estadio
//     GEMINI_IMAGE_MODEL=gemini-3-pro-image node art/generate.mjs
//
// Escribe en `commons/brand/art/<id>.jpg`. Despues, `npm run build` o el
// servidor de desarrollo las recogen solas (`commons/brand/art.ts`).

import { existsSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { apiKey, extensionFor, findImage, generateContentBody, interactionsBody, pending, redact } from "./lib.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const OUT = path.resolve(HERE, "..", "commons", "brand", "art");
const ENV_FILE = path.join(HERE, ".env.local");
const API = "https://generativelanguage.googleapis.com/v1beta";
const MODEL = process.env.GEMINI_IMAGE_MODEL?.trim() || "gemini-3.1-flash-image";

const args = process.argv.slice(2);
const force = args.includes("--force");
const onlyAt = args.indexOf("--only");
const only = onlyAt >= 0 ? (args[onlyAt + 1] ?? "").split(",").filter(Boolean) : [];

const key = apiKey(process.env, existsSync(ENV_FILE) ? readFileSync(ENV_FILE, "utf-8") : null);
if (!key) {
  console.error(
    "Falta la clave de Google AI Studio. Guardala en frontend/art/.env.local como GEMINI_API_KEY=... " +
      "(git la ignora) o exporta GEMINI_API_KEY. No la pegues en ningun chat.",
  );
  process.exit(2);
}

const catalog = JSON.parse(readFileSync(path.join(OUT, "catalog.json"), "utf-8"));
const todo = pending(
  catalog.images.map((i) => i.id),
  readdirSync(OUT).filter((f) => /\.(jpg|png)$/.test(f)),
  { force, only },
);
if (todo.length === 0) {
  console.log("Nada que generar: el catalogo esta completo. Usa --force para regenerarlo.");
  process.exit(0);
}

async function post(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "x-goog-api-key": key, "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    // no es JSON: se informa con el texto
  }
  return { status: response.status, json, text: redact(text, key) };
}

/** Interacciones primero; `generateContent` si la ruta nueva no existe para esta cuenta o este modelo (D-120). */
async function generate(prompt, aspect) {
  const first = await post(`${API}/interactions`, interactionsBody(MODEL, prompt, aspect));
  const image = first.status === 200 ? findImage(first.json) : null;
  if (image) return image;
  const second = await post(`${API}/models/${encodeURIComponent(MODEL)}:generateContent`, generateContentBody(prompt, aspect));
  const fallback = second.status === 200 ? findImage(second.json) : null;
  if (fallback) return fallback;
  const worst = second.status !== 404 ? second : first;
  throw new Error(`HTTP ${worst.status}: ${worst.text.slice(0, 600)}`);
}

async function withRetry(fn) {
  for (let attempt = 1; ; attempt++) {
    try {
      return await fn();
    } catch (error) {
      const retriable = /HTTP (429|5\d\d)/.test(String(error.message));
      if (!retriable || attempt >= 3) throw error;
      await new Promise((r) => setTimeout(r, 8000 * attempt));
    }
  }
}

let failed = 0;
console.log(`Modelo ${MODEL}. ${todo.length} ilustraciones: ${todo.join(", ")}`);
for (const id of todo) {
  const entry = catalog.images.find((i) => i.id === id);
  const prompt = `${catalog.style}\n\n${entry.prompt}`;
  try {
    const image = await withRetry(() => generate(prompt, entry.aspect));
    const ext = extensionFor(image.mime);
    if (!ext) throw new Error(`tipo de imagen no esperado: ${image.mime}`);
    const bytes = Buffer.from(image.data, "base64");
    writeFileSync(path.join(OUT, `${id}.${ext}`), bytes);
    console.log(`  ok  ${id}.${ext} (${Math.round(bytes.length / 1024)} KB)`);
  } catch (error) {
    failed += 1;
    console.error(`  FALLA ${id}: ${redact(String(error.message), key)}`);
  }
}
console.log(failed ? `\n${failed} ilustraciones fallaron` : "\nCatalogo generado");
process.exit(failed ? 1 : 0);
