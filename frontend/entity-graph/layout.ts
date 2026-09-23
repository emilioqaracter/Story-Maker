/**
 * Posicion de los nodos del grafo de entidades. Pura y determinista (RNF-47):
 * el mismo canon dibuja el mismo grafo, se pida cuando se pida.
 *
 * Circulo ordenado por identificador. No es el mejor dibujo posible para una
 * obra con cien personajes, pero no depende de ninguna libreria, y la libreria
 * de dibujo es una decision abierta (`architecture.md` §2.2, D-57).
 */

export interface Point {
  x: number;
  y: number;
}

export const SIZE = 480;
const MARGIN = 70;

export function layout(ids: readonly string[]): Map<string, Point> {
  const sorted = [...new Set(ids)].sort();
  const out = new Map<string, Point>();
  const center = SIZE / 2;
  const radius = center - MARGIN;
  sorted.forEach((id, i) => {
    if (sorted.length === 1) {
      out.set(id, { x: center, y: center });
      return;
    }
    const angle = (2 * Math.PI * i) / sorted.length - Math.PI / 2;
    out.set(id, { x: round(center + radius * Math.cos(angle)), y: round(center + radius * Math.sin(angle)) });
  });
  return out;
}

function round(n: number): number {
  return Math.round(n * 100) / 100;
}
