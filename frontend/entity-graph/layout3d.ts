/**
 * Posicion 3D de las entidades y su proyeccion (`specs/srs-frontend-v2.md` RF-283, D-118).
 *
 * Puras y deterministas (RNF-47): el mismo canon da la misma figura. Las
 * entidades salen de una espiral de Fibonacci sobre la esfera, en orden de
 * identificador, y se relajan un numero fijo de pasos: se repelen entre si y
 * las relacionadas se atraen. Al final la figura se centra y se escala hasta
 * la esfera unidad. Sin libreria (D-57): cien entidades son diez mil pares por
 * paso, que el navegador resuelve en milisegundos.
 */

export interface Point3 {
  x: number;
  y: number;
  z: number;
}

export interface Projected {
  x: number;
  y: number;
  /** Aumento por la perspectiva: mayor que 1 delante del centro, menor detras. */
  scale: number;
  /** Profundidad tras girar, en [-1, 1]: positiva hacia quien mira. */
  depth: number;
}

const GOLDEN = Math.PI * (3 - Math.sqrt(5));
const STEPS = 160;

function round(n: number): number {
  return Math.round(n * 1e4) / 1e4;
}

/** Posiciones en la esfera unidad, por identificador. */
export function layout3d(ids: readonly string[], edges: readonly (readonly [string, string])[]): Map<string, Point3> {
  const sorted = [...new Set(ids)].sort();
  const n = sorted.length;
  const out = new Map<string, Point3>();
  if (n === 0) return out;
  if (n === 1) {
    out.set(sorted[0] ?? "", { x: 0, y: 0, z: 0 });
    return out;
  }

  const index = new Map(sorted.map((id, i) => [id, i]));
  const pos = sorted.map((_, i) => {
    const y = 1 - (2 * (i + 0.5)) / n;
    const r = Math.sqrt(1 - y * y);
    const t = GOLDEN * i;
    return { x: Math.cos(t) * r, y, z: Math.sin(t) * r };
  });
  const links = new Set<string>();
  const pairs: [number, number][] = [];
  for (const [a, b] of edges) {
    const i = index.get(a);
    const j = index.get(b);
    if (i === undefined || j === undefined || i === j) continue;
    const k = i < j ? `${i}:${j}` : `${j}:${i}`;
    if (links.has(k)) continue;
    links.add(k);
    pairs.push(i < j ? [i, j] : [j, i]);
  }
  // Orden canonico: sumar las fuerzas en otro orden daria otros redondeos, y otra figura.
  pairs.sort((p, q) => p[0] - q[0] || p[1] - q[1]);

  // Distancia de reposo: la que tendrian n puntos repartidos por igual en la esfera.
  const rest = 2.2 / Math.sqrt(n);
  for (let step = 0; step < STEPS; step++) {
    const cool = 0.12 * (1 - step / STEPS) + 0.005;
    const force = pos.map(() => ({ x: 0, y: 0, z: 0 }));
    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = pos[i];
        const b = pos[j];
        const fi = force[i];
        const fj = force[j];
        if (!a || !b || !fi || !fj) continue;
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const dz = a.z - b.z;
        const d2 = Math.max(dx * dx + dy * dy + dz * dz, 1e-4);
        const push = (rest * rest) / d2;
        fi.x += dx * push;
        fi.y += dy * push;
        fi.z += dz * push;
        fj.x -= dx * push;
        fj.y -= dy * push;
        fj.z -= dz * push;
      }
    }
    for (const [i, j] of pairs) {
      const a = pos[i];
      const b = pos[j];
      const fi = force[i];
      const fj = force[j];
      if (!a || !b || !fi || !fj) continue;
      const dx = b.x - a.x;
      const dy = b.y - a.y;
      const dz = b.z - a.z;
      const d = Math.max(Math.sqrt(dx * dx + dy * dy + dz * dz), 1e-3);
      const pull = (d - rest) / d;
      fi.x += dx * pull;
      fi.y += dy * pull;
      fi.z += dz * pull;
      fj.x -= dx * pull;
      fj.y -= dy * pull;
      fj.z -= dz * pull;
    }
    pos.forEach((p, i) => {
      const f = force[i];
      if (!f) return;
      // Una gravedad suave al centro, para que un grupo sin relaciones no se escape.
      f.x -= p.x * 0.3;
      f.y -= p.y * 0.3;
      f.z -= p.z * 0.3;
      const len = Math.sqrt(f.x * f.x + f.y * f.y + f.z * f.z);
      const k = len > cool ? cool / len : 1;
      p.x += f.x * k;
      p.y += f.y * k;
      p.z += f.z * k;
    });
  }

  const c = pos.reduce((s, p) => ({ x: s.x + p.x / n, y: s.y + p.y / n, z: s.z + p.z / n }), { x: 0, y: 0, z: 0 });
  const far = Math.max(...pos.map((p) => Math.hypot(p.x - c.x, p.y - c.y, p.z - c.z)), 1e-9);
  sorted.forEach((id, i) => {
    const p = pos[i];
    if (!p) return;
    out.set(id, { x: round((p.x - c.x) / far), y: round((p.y - c.y) / far), z: round((p.z - c.z) / far) });
  });
  return out;
}

/** Gira un punto: primero alrededor del eje vertical (`yaw`), despues del horizontal (`pitch`). */
export function rotate(p: Point3, yaw: number, pitch: number): Point3 {
  const cy = Math.cos(yaw);
  const sy = Math.sin(yaw);
  const x = p.x * cy + p.z * sy;
  const z1 = -p.x * sy + p.z * cy;
  const cp = Math.cos(pitch);
  const sp = Math.sin(pitch);
  return { x, y: p.y * cp - z1 * sp, z: p.y * sp + z1 * cp };
}

/** Distancia de la camara al centro, en radios de la esfera. */
export const CAMERA = 3.2;

/** Proyeccion en perspectiva sobre un lienzo de `size` con la esfera de `radius` pixeles. */
export function project(p: Point3, size: number, radius: number): Projected {
  const scale = CAMERA / (CAMERA - Math.max(-1, Math.min(1, p.z)));
  return { x: size / 2 + p.x * radius * scale, y: size / 2 + p.y * radius * scale, scale, depth: p.z };
}
