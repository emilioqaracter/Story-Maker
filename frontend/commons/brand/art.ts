/**
 * Las ilustraciones deportivas del catalogo (`specs/srs-frontend-v2.md` RF-275 a RF-278).
 *
 * Las genera en desarrollo `art/generate.mjs` y viven en `commons/brand/art/`
 * como JPEG (o PNG, si el modelo lo devuelve asi) versionados: la aplicacion no llama a nadie para tenerlas (RNF-59).
 * Se resuelven en la construccion; una que todavia no exista devuelve
 * `undefined` y quien la pinta pone el degradado de la marca (RF-277).
 */
import catalog from "./art/catalog.json";

export type ArtId = (typeof catalog.images)[number]["id"];

/** Las relaciones de aspecto que admite el modelo de imagen (D-120). */
export const ASPECTS = ["1:1", "3:2", "2:3", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"] as const;

export const CATALOG: readonly { id: string; use: string; aspect: string; prompt: string }[] = catalog.images;
export const STYLE: string = catalog.style;

const files = import.meta.glob<string>("./art/*.{jpg,png}", { eager: true, query: "?url", import: "default" });

/** Direccion de la ilustracion en el sitio construido, o `undefined` si no se ha generado. */
export function illustration(id: ArtId): string | undefined {
  return files[`./art/${id}.jpg`] ?? files[`./art/${id}.png`];
}

/** Las portadas de novela del catalogo, en su orden. */
export const COVERS: readonly ArtId[] = catalog.images.filter((i) => i.id.startsWith("portada-")).map((i) => i.id);

/** FNV-1a de 32 bits. Pura. */
export function fnv1a(text: string): number {
  let hash = 0x811c9dc5;
  for (let i = 0; i < text.length; i++) {
    hash ^= text.charCodeAt(i);
    hash = Math.imul(hash, 0x01000193) >>> 0;
  }
  return hash >>> 0;
}

/** La portada de una novela: la misma novela, siempre la misma (RF-278, D-116). Pura. */
export function coverFor(novelId: string): ArtId {
  const cover = COVERS[fnv1a(novelId) % COVERS.length];
  if (cover === undefined) throw new Error("El catalogo no tiene portadas");
  return cover;
}
