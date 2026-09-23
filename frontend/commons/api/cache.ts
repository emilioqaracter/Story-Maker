/**
 * Cache de respuestas por novela y version (RD-28).
 *
 * El frontend no guarda canon: guarda respuestas, y las suelta cuando el backend
 * dice que algo cambio. La version que se esta escribiendo crece con cada
 * capitulo congelado, asi que la cache de una novela se invalida cuando RI-03
 * muestra un capitulo congelado mas o la tirada cambia de estado de cierre.
 * La logica es pura (RNF-47); el almacen de abajo solo la aplica.
 */

/** Lo que de RI-03 decide si la cache de una novela sigue valiendo. */
export interface Snapshot {
  frozenChapters: number;
  closed: boolean | null;
}

export function cacheKey(novel: string, version: number, resource: string): string {
  return `${novel}\u0000${version}\u0000${resource}`;
}

function novelOf(key: string): string {
  return key.split("\u0000", 1)[0] ?? "";
}

/** Si el estado nuevo de la tirada obliga a soltar la cache de la novela. */
export function changed(previous: Snapshot | undefined, next: Snapshot): boolean {
  if (previous === undefined) return false;
  return previous.frozenChapters !== next.frozenChapters || previous.closed !== next.closed;
}

/** Las entradas que sobreviven a invalidar una novela: las de las demas, intactas. */
export function invalidate<V>(entries: ReadonlyMap<string, V>, novel: string): Map<string, V> {
  const out = new Map<string, V>();
  for (const [key, value] of entries) {
    if (novelOf(key) !== novel) out.set(key, value);
  }
  return out;
}

type Listener = () => void;

/** El almacen que usan los componentes. Uno por aplicacion. */
export class ResponseCache {
  private entries = new Map<string, unknown>();
  private snapshots = new Map<string, Snapshot>();
  private listeners = new Set<Listener>();

  readonly subscribe = (listener: Listener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  get(key: string): unknown {
    return this.entries.get(key);
  }

  set(key: string, value: unknown): void {
    this.entries.set(key, value);
    this.emit();
  }

  /** Aplica el estado de la tirada que acaba de llegar de RI-03. */
  observe(novel: string, next: Snapshot): void {
    const previous = this.snapshots.get(novel);
    this.snapshots.set(novel, next);
    if (changed(previous, next)) {
      this.entries = invalidate(this.entries, novel);
      this.emit();
    }
  }

  /** Suelta la cache de una novela: una version nueva aparecio (RF-190). */
  invalidateNovel(novel: string): void {
    this.entries = invalidate(this.entries, novel);
    this.emit();
  }

  clear(): void {
    this.entries = new Map();
    this.snapshots = new Map();
    this.emit();
  }

  private emit(): void {
    for (const listener of this.listeners) listener();
  }
}

export const cache = new ResponseCache();
