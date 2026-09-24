/**
 * Las partes puras del generador de ilustraciones (`specs/srs-frontend-v2.md` RF-276, RNF-60).
 *
 * `generate.mjs` las importa con la eliminacion de tipos de Node, y las pruebas
 * las comprueban sin clave y sin red: por eso solo hay sintaxis que se borra,
 * sin enums ni espacios de nombres.
 */

/** Las variables de un fichero `.env`: `CLAVE=valor`, comentarios con `#`, comillas opcionales. */
export function parseEnv(text: string): Map<string, string> {
  const out = new Map<string, string>();
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#")) continue;
    const eq = line.indexOf("=");
    if (eq <= 0) continue;
    const key = line.slice(0, eq).trim().replace(/^export\s+/, "");
    const value = line.slice(eq + 1).trim().replace(/^(['"])(.*)\1$/, "$2");
    if (value) out.set(key, value);
  }
  return out;
}

const KEY_NAMES = ["GEMINI_API_KEY", "GOOGLE_API_KEY"] as const;

/** La clave: primero el entorno, despues `art/.env.local`. `undefined` si no hay ninguna. */
export function apiKey(env: Readonly<Record<string, string | undefined>>, fileText: string | null): string | undefined {
  for (const name of KEY_NAMES) {
    const value = env[name]?.trim();
    if (value) return value;
  }
  const file = fileText === null ? new Map<string, string>() : parseEnv(fileText);
  for (const name of KEY_NAMES) {
    const value = file.get(name);
    if (value) return value;
  }
  return undefined;
}

/** Quita la clave de cualquier texto antes de mostrarlo (RNF-60). */
export function redact(text: string, key: string): string {
  return key ? text.split(key).join("[CLAVE]") : text;
}

/** Cuerpo de la API de interacciones de Gemini (D-120). */
export function interactionsBody(model: string, prompt: string, aspect: string) {
  return {
    model,
    input: [{ type: "text", text: prompt }],
    response_format: { type: "image", mime_type: "image/jpeg", aspect_ratio: aspect, image_size: "1K" },
  };
}

/** Cuerpo de `generateContent`, la ruta de respaldo (D-120). */
export function generateContentBody(prompt: string, aspect: string) {
  return {
    contents: [{ role: "user", parts: [{ text: prompt }] }],
    generationConfig: { responseModalities: ["IMAGE"], imageConfig: { aspectRatio: aspect } },
  };
}

export interface FoundImage {
  mime: string;
  data: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

/**
 * La primera imagen en base64 de una respuesta, se llame como se llame el campo:
 * `inlineData` en `generateContent`, `output_image` o bloques de salida en la de
 * interacciones. Un objeto con `data` y un tipo `image/*` es una imagen.
 */
export function findImage(json: unknown, depth = 0): FoundImage | null {
  if (depth > 12 || !isRecord(json)) return null;
  const mime = json.mime_type ?? json.mimeType;
  if (typeof json.data === "string" && json.data.length > 64 && typeof mime === "string" && mime.startsWith("image/")) {
    return { mime, data: json.data };
  }
  for (const value of Array.isArray(json) ? json : Object.values(json)) {
    const found = findImage(value, depth + 1);
    if (found) return found;
  }
  return null;
}

/** Extension del fichero para el tipo que devolvio el modelo. */
export function extensionFor(mime: string): "jpg" | "png" | null {
  if (mime === "image/jpeg" || mime === "image/jpg") return "jpg";
  if (mime === "image/png") return "png";
  return null;
}

/** Las ilustraciones que hay que generar: las que faltan, o todas con `force`, acotadas a `only` si se da. */
export function pending(
  ids: readonly string[],
  existing: readonly string[],
  options: { force: boolean; only: readonly string[] },
): string[] {
  const have = new Set(existing.map((f) => f.replace(/\.(jpg|png)$/, "")));
  return ids.filter((id) => (options.only.length === 0 || options.only.includes(id)) && (options.force || !have.has(id)));
}
