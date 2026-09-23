/**
 * De una seleccion en la lectura a un ancla de fragmento (RF-187, RD-30).
 *
 * La cita se toma del **texto fuente** de la escena por desplazamientos, no de
 * `Selection.toString()`: el navegador inserta saltos entre parrafos y colapsa
 * espacios segun el CSS, y lo que devuelve no siempre es una subcadena del
 * texto. No se recorta, no se normaliza y no se completa: la regla de anclaje la
 * aplica el backend (`verification.md` §5.11).
 */

import { SCENE_ATTRIBUTE } from "../reading/attribute";

export interface FragmentAnchor {
  kind: "fragment";
  version: number;
  chapter: number;
  scene_id: string;
  quote: string;
}

/** La cita exacta entre dos desplazamientos del texto de la escena, en cualquier orden. Pura. */
export function quoteBetween(sceneText: string, a: number, b: number): string {
  const [start, end] = a <= b ? [a, b] : [b, a];
  return sceneText.slice(Math.max(0, start), Math.min(sceneText.length, end));
}

/** Desplazamiento en el texto de la escena de un punto de la seleccion, o `null` si cae fuera de un parrafo. */
export function offsetOf(node: Node | null, offset: number): number | null {
  if (node === null) return null;
  const paragraph = (node instanceof Element ? node : node.parentElement)?.closest("[data-offset]");
  if (!paragraph) return null;
  const base = Number(paragraph.getAttribute("data-offset"));
  if (!Number.isFinite(base)) return null;
  if (node.nodeType !== Node.TEXT_NODE) return base;
  return base + offset;
}

/** RF-187. El ancla de una seleccion dentro de exactamente una escena, o `null`. */
export function anchorFromSelection(
  selection: Selection | null,
  texts: ReadonlyMap<string, string>,
  version: number,
  chapter: number,
): FragmentAnchor | null {
  if (selection === null || selection.isCollapsed || selection.rangeCount === 0) return null;
  const scene = (n: Node | null) =>
    (n instanceof Element ? n : (n?.parentElement ?? null))?.closest(`[${SCENE_ATTRIBUTE}]`)?.getAttribute(SCENE_ATTRIBUTE) ?? null;
  const sceneId = scene(selection.anchorNode);
  if (sceneId === null || sceneId !== scene(selection.focusNode)) return null;
  const text = texts.get(sceneId);
  const a = offsetOf(selection.anchorNode, selection.anchorOffset);
  const b = offsetOf(selection.focusNode, selection.focusOffset);
  if (text === undefined || a === null || b === null) return null;
  const quote = quoteBetween(text, a, b);
  return quote ? { kind: "fragment", version, chapter, scene_id: sceneId, quote } : null;
}
