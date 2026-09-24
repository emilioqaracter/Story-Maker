/**
 * El veredicto del recorrido visual (`specs/srs-backend-v4.md` RF-267, D-96). Puro:
 * recibe lo que sirve la API y lo que pinta la pagina, y dice que pasa, que
 * falla y a que rol vuelve cada fallo. `tour.mjs` lo alimenta desde el navegador.
 *
 * La regla de reparto, una sola para todas las comprobaciones: si el dato no
 * llega bien de la API es un defecto de datos y vuelve al backend; si llega
 * bien y la pagina no lo muestra, es de presentacion y vuelve al frontend como
 * prueba en rojo. Ninguno reabre un capitulo: el frontend observa, no corrige
 * (`AGENTS.md` §3.1).
 *
 * Sin importaciones a proposito: lo carga Node directamente desde `tour.mjs` y
 * lo prueba vitest en la puerta.
 */

export type Role = "backend" | "frontend";

export interface Side {
  ok: boolean;
  detail: string;
}

export interface Check {
  id: string;
  what: string;
  ok: boolean;
  role: Role | null;
  detail: string;
}

/** Lo que el recorrido usa del manifiesto de RI-43. */
export interface ManifestView {
  title: string;
  dedication: string;
  recipient_name: string;
  chapters: readonly number[];
}

/** Lo que la portada pinta: `null` si el nodo no esta. */
export interface CoverView {
  title: string | null;
  dedication: string | null;
  hint: string | null;
}

export interface LinkView {
  text: string;
  href: string;
}

export interface ChapterView {
  heading: string | null;
  /** Escenas pintadas. */
  scenes: number;
  /** De ellas, las que no tienen texto. */
  empty: number;
}

export interface EntityApi {
  name: string;
  chapters: readonly number[];
}

export interface BibleView {
  personListed: boolean;
  placeListed: boolean;
  heading: string | null;
  /** Capitulo de cada enlace de «Dónde aparece». */
  appearances: readonly number[];
}

const OK: Side = { ok: true, detail: "" };
const side = (ok: boolean, detail: string): Side => (ok ? OK : { ok: false, detail });
const clean = (s: string | null): string => (s ?? "").replace(/\s+/g, " ").trim();

/** La regla de reparto. */
export function judge(id: string, what: string, data: Side, page: Side): Check {
  if (!data.ok) return { id, what, ok: false, role: "backend", detail: data.detail };
  if (!page.ok) return { id, what, ok: false, role: "frontend", detail: page.detail };
  return { id, what, ok: true, role: null, detail: "" };
}

/** Titulo, dedicatoria y destinatario: no vacios en el manifiesto y pintados tal cual. */
export function coverChecks(m: ManifestView, page: CoverView): Check[] {
  const shown = (field: string, served: string, painted: string | null): Side => {
    const p = clean(painted);
    if (painted === null) return side(false, `la portada no pinta ${field}`);
    return side(p === clean(served), `la portada pinta ${field} «${p}» y el manifiesto sirve «${clean(served)}»`);
  };
  const para = clean(page.hint);
  return [
    judge(
      "portada.titulo",
      "La portada muestra el título de la novela",
      side(clean(m.title) !== "", "el manifiesto de RI-43 llega sin título"),
      shown("el título", m.title, page.title),
    ),
    judge(
      "portada.dedicatoria",
      "La portada muestra la dedicatoria",
      side(clean(m.dedication) !== "", "el manifiesto de RI-43 llega sin dedicatoria: el brief de la novela no la guarda"),
      shown("la dedicatoria", m.dedication, page.dedication),
    ),
    judge(
      "portada.destinatario",
      "La portada dice para quién es la novela",
      side(clean(m.recipient_name) !== "", "el manifiesto de RI-43 llega sin destinatario"),
      side(
        para.includes(clean(m.recipient_name)) && page.hint !== null,
        page.hint === null ? "la portada no dice para quién es" : `la portada dice «${para}» y el destinatario es «${clean(m.recipient_name)}»`,
      ),
    ),
  ];
}

/** El capitulo al que apunta un enlace de lectura. */
export const chapterOf = (href: string): number | null => {
  const m = /\/chapters\/(\d+)(?:[#?].*)?$/.exec(href);
  return m ? Number(m[1]) : null;
};

/** Un enlace por capitulo congelado, en orden, a su lectura en la version que se lee (RF-178). */
export function tocCheck(novel: string, version: number, m: ManifestView, frozen: number, page: readonly LinkView[]): Check {
  const expected = [...m.chapters].sort((a, b) => a - b);
  const data = side(
    expected.length === frozen,
    `RI-03 dice ${frozen} capítulos congelados y el manifiesto de RI-43 lista ${expected.length}`,
  );
  const base = `/app/novels/${novel}/v/${version}/chapters/`;
  const got = page.map((l) => (l.href.startsWith(base) ? chapterOf(l.href) : null));
  const same = got.length === expected.length && got.every((n, i) => n === expected[i]);
  return judge(
    "indice",
    "El índice tiene un enlace por capítulo congelado",
    data,
    side(same, `el índice enlaza [${got.join(", ")}] y los capítulos congelados son [${expected.join(", ")}]`),
  );
}

/** Un capitulo abierto desde el indice o la navegacion: su titulo y sus escenas con texto. */
export function chapterCheck(number: number, servedScenes: number, page: ChapterView): Check {
  const heading = clean(page.heading);
  const problems = [
    heading !== `Capítulo ${number}` && `el título es «${heading}»`,
    page.scenes !== servedScenes && `pinta ${page.scenes} escenas y RI-44 sirve ${servedScenes}`,
    page.empty > 0 && `${page.empty} escenas sin texto`,
  ].filter((p): p is string => typeof p === "string");
  return judge(
    `capitulo.${number}`,
    `El capítulo ${number} se lee con sus escenas`,
    side(servedScenes > 0, `RI-44 sirve el capítulo ${number} sin escenas`),
    side(problems.length === 0, problems.join("; ")),
  );
}

/** La ficha: la persona y el lugar en sus pestanas, y la persona con un enlace a cada capitulo donde aparece. */
export function bibleChecks(api: { person: EntityApi; place: EntityApi }, page: BibleView): Check[] {
  const want = [...new Set(api.person.chapters)].sort((a, b) => a - b);
  const got = [...new Set(page.appearances)].sort((a, b) => a - b);
  const same = got.length === want.length && got.every((n, i) => n === want[i]);
  return [
    judge(
      "ficha.personaje",
      "La ficha del personaje enlaza los capítulos donde aparece",
      side(want.length > 0, `RI-46 no da capítulos para «${api.person.name}»`),
      side(
        page.personListed && clean(page.heading) === clean(api.person.name) && same,
        !page.personListed
          ? `«${api.person.name}» no está en la pestaña Personajes`
          : clean(page.heading) !== clean(api.person.name)
            ? `la ficha se titula «${clean(page.heading)}»`
            : `la ficha enlaza los capítulos [${got.join(", ")}] y aparece en [${want.join(", ")}]`,
      ),
    ),
    judge(
      "ficha.lugar",
      "El lugar está en la pestaña Lugares",
      side(clean(api.place.name) !== "", "RI-45 no sirve ningún lugar"),
      side(page.placeListed, `«${api.place.name}» no está en la pestaña Lugares`),
    ),
  ];
}

/** `2026-09-23T14-05-09Z-caso`: fecha al segundo, sin `:`, que Windows no admite en un nombre. */
export function resultName(date: Date, caso: string): string {
  return `${date.toISOString().slice(0, 19).replace(/:/g, "-")}Z-${caso}`;
}

export interface VisualRecord {
  fecha: string;
  caso: string;
  novela: string;
  commit: string;
  resultado: "pasa" | "falla";
  vuelve_a: Role[];
  fallos: Check[];
  comprobaciones: Check[];
  evidencia: string[];
  nota: string;
}

const NOTA =
  "Un fallo del backend es un defecto de datos: la versión no se publica hasta que la API sirva lo que falta. " +
  "Un fallo del frontend es una prueba en rojo de la presentación. No reabre ningún capítulo: el frontend observa, no corrige (AGENTS.md §3.1).";

export function record(r: {
  caso: string;
  novel: string;
  date: Date;
  commit: string;
  checks: readonly Check[];
  evidence: readonly string[];
}): VisualRecord {
  const fallos = r.checks.filter((c) => !c.ok);
  const roles: Role[] = (["backend", "frontend"] as const).filter((role) => fallos.some((f) => f.role === role));
  return {
    fecha: r.date.toISOString(),
    caso: r.caso,
    novela: r.novel,
    commit: r.commit,
    resultado: fallos.length === 0 ? "pasa" : "falla",
    vuelve_a: roles,
    fallos,
    comprobaciones: [...r.checks],
    evidencia: [...r.evidence],
    nota: NOTA,
  };
}

/** La puerta de T49: la copia sana pasa y la copia sin dedicatoria falla por la dedicatoria, y vuelve al backend. */
export function gateOutcome(sana: VisualRecord, sinDedicatoria: VisualRecord): Side {
  if (sana.resultado !== "pasa") {
    return side(false, `la copia sana falla: ${sana.fallos.map((f) => `${f.id} (${f.role}): ${f.detail}`).join("; ")}`);
  }
  const d = sinDedicatoria.fallos.find((f) => f.id === "portada.dedicatoria");
  if (sinDedicatoria.resultado !== "falla" || d === undefined) {
    return side(false, "la copia sin dedicatoria no falla por la dedicatoria");
  }
  if (d.role !== "backend") return side(false, `la dedicatoria que falta vuelve a ${d.role}, no al backend`);
  return OK;
}
