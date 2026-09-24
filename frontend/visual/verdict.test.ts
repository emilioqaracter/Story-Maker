import fc from "fast-check";
import { describe, expect, it } from "vitest";

import {
  bibleChecks,
  chapterCheck,
  coverChecks,
  gateOutcome,
  judge,
  record,
  resultName,
  tocCheck,
  type ChapterView,
  type Check,
  type CoverView,
  type ManifestView,
} from "./verdict";

const NOVEL = "novela-visual";

const manifest = (over: Partial<ManifestView> = {}): ManifestView => ({
  title: "El verano del faro",
  dedication: "Para Irene",
  recipient_name: "Irene",
  chapters: [1, 2, 3],
  ...over,
});

const links = (chapters: readonly number[]) =>
  chapters.map((n) => ({ text: `Capítulo ${n}`, href: `/app/novels/${NOVEL}/v/1/chapters/${n}` }));

const cover = (over: Partial<CoverView> = {}): CoverView => ({
  title: "El verano del faro",
  dedication: "Para Irene",
  hint: "Una novela para Irene",
  ...over,
});

const byId = (checks: readonly Check[], id: string) => checks.find((c) => c.id === id);

describe("a que rol vuelve un fallo visual (RF-267)", () => {
  it("un dato que falta en la API es del backend aunque la pantalla tambien falle", () => {
    const c = judge("x", "algo", { ok: false, detail: "sin dato" }, { ok: false, detail: "sin nodo" });
    expect(c).toMatchObject({ ok: false, role: "backend", detail: "sin dato" });
  });

  it("con el dato bien servido, lo que la pantalla no muestra es del frontend", () => {
    const c = judge("x", "algo", { ok: true, detail: "" }, { ok: false, detail: "sin nodo" });
    expect(c).toMatchObject({ ok: false, role: "frontend", detail: "sin nodo" });
  });

  it("el rol es el backend si y solo si falla el dato, y nada falla si los dos lados pasan", () => {
    fc.assert(
      fc.property(fc.boolean(), fc.boolean(), (data, page) => {
        const c = judge("x", "algo", { ok: data, detail: "d" }, { ok: page, detail: "p" });
        expect(c.ok).toBe(data && page);
        expect(c.role).toBe(!data ? "backend" : !page ? "frontend" : null);
      }),
    );
  });
});

describe("portada", () => {
  it("pasa con titulo, dedicatoria y destinatario servidos y mostrados", () => {
    expect(coverChecks(manifest(), cover()).every((c) => c.ok)).toBe(true);
  });

  it("un manifiesto sin dedicatoria es un fallo del backend", () => {
    const c = byId(coverChecks(manifest({ dedication: "" }), cover({ dedication: null })), "portada.dedicatoria");
    expect(c).toMatchObject({ ok: false, role: "backend" });
    expect(c?.detail).toContain("RI-43");
  });

  it("una dedicatoria servida que la portada no pinta es un fallo del frontend", () => {
    const c = byId(coverChecks(manifest(), cover({ dedication: null })), "portada.dedicatoria");
    expect(c).toMatchObject({ ok: false, role: "frontend" });
  });

  it("una dedicatoria pintada distinta de la servida es un fallo del frontend", () => {
    const c = byId(coverChecks(manifest(), cover({ dedication: "Para otra" })), "portada.dedicatoria");
    expect(c).toMatchObject({ ok: false, role: "frontend" });
  });

  it("titulo y destinatario siguen la misma regla", () => {
    const sinTitulo = coverChecks(manifest({ title: "" }), cover({ title: "" }));
    expect(byId(sinTitulo, "portada.titulo")).toMatchObject({ ok: false, role: "backend" });
    const sinPara = coverChecks(manifest(), cover({ hint: null }));
    expect(byId(sinPara, "portada.destinatario")).toMatchObject({ ok: false, role: "frontend" });
  });
});

describe("indice", () => {
  it("pasa con un enlace por capitulo congelado, en orden y a su lectura", () => {
    expect(tocCheck(NOVEL, 1, manifest(), 3, links([1, 2, 3])).ok).toBe(true);
  });

  it("un manifiesto que no lista todos los capitulos congelados es del backend", () => {
    expect(tocCheck(NOVEL, 1, manifest({ chapters: [1, 2] }), 3, links([1, 2]))).toMatchObject({ ok: false, role: "backend" });
  });

  it("un indice al que le falta un enlace, o que apunta mal, es del frontend", () => {
    expect(tocCheck(NOVEL, 1, manifest(), 3, links([1, 3]))).toMatchObject({ ok: false, role: "frontend" });
    const mal = links([1, 2, 3]).map((l, i) => (i === 1 ? { ...l, href: `/app/novels/${NOVEL}/v/1/chapters/9` } : l));
    expect(tocCheck(NOVEL, 1, manifest(), 3, mal)).toMatchObject({ ok: false, role: "frontend" });
  });
});

describe("capitulo", () => {
  const view = (over: Partial<ChapterView> = {}): ChapterView => ({ heading: "Capítulo 2", scenes: 1, empty: 0, ...over });

  it("pasa con su titulo y tantas escenas con texto como sirve RI-44", () => {
    expect(chapterCheck(2, 1, view()).ok).toBe(true);
  });

  it("sin escenas en la API es del backend; sin escenas en pantalla, del frontend", () => {
    expect(chapterCheck(2, 0, view({ scenes: 0 }))).toMatchObject({ ok: false, role: "backend" });
    expect(chapterCheck(2, 1, view({ scenes: 0 }))).toMatchObject({ ok: false, role: "frontend" });
    expect(chapterCheck(2, 1, view({ empty: 1 }))).toMatchObject({ ok: false, role: "frontend" });
    expect(chapterCheck(2, 1, view({ heading: "Capítulo 3" }))).toMatchObject({ ok: false, role: "frontend" });
  });
});

describe("ficha de personajes y lugares", () => {
  const api = { person: { name: "Irene", chapters: [1, 2, 3] }, place: { name: "el faro", chapters: [1, 2, 3] } };
  const page = { personListed: true, placeListed: true, heading: "Irene", appearances: [1, 1, 2, 3] };

  it("pasa si la persona y el lugar estan en sus pestanas y la ficha enlaza cada capitulo en que aparece", () => {
    expect(bibleChecks(api, page).every((c) => c.ok)).toBe(true);
  });

  it("una entidad sin capitulos en la API es del backend", () => {
    const c = byId(bibleChecks({ ...api, person: { name: "Irene", chapters: [] } }, page), "ficha.personaje");
    expect(c).toMatchObject({ ok: false, role: "backend" });
  });

  it("una ficha que no enlaza un capitulo, o no lista el lugar, es del frontend", () => {
    expect(byId(bibleChecks(api, { ...page, appearances: [1, 2] }), "ficha.personaje")).toMatchObject({ ok: false, role: "frontend" });
    expect(byId(bibleChecks(api, { ...page, placeListed: false }), "ficha.lugar")).toMatchObject({ ok: false, role: "frontend" });
  });
});

describe("registro fechado", () => {
  const when = new Date("2026-09-23T14:05:09.123Z");

  it("el nombre del fichero lleva la fecha y el caso, sin caracteres que Windows no admite", () => {
    expect(resultName(when, "sin-dedicatoria")).toBe("2026-09-23T14-05-09Z-sin-dedicatoria");
  });

  it("un recorrido con un fallo falla, dice a que roles vuelve y que no reabre ningun capitulo", () => {
    const checks = coverChecks(manifest({ dedication: "" }), cover({ dedication: null }));
    const r = record({ caso: "sin-dedicatoria", novel: NOVEL, date: when, commit: "abc1234", checks, evidence: [] });
    expect(r).toMatchObject({ fecha: "2026-09-23T14:05:09.123Z", resultado: "falla", vuelve_a: ["backend"] });
    expect(r.fallos.map((f) => f.id)).toEqual(["portada.dedicatoria"]);
    expect(r.nota).toContain("No reabre ningún capítulo");
  });

  it("un recorrido limpio pasa y no vuelve a nadie", () => {
    const r = record({ caso: "sana", novel: NOVEL, date: when, commit: "abc1234", checks: coverChecks(manifest(), cover()), evidence: [] });
    expect(r).toMatchObject({ resultado: "pasa", vuelve_a: [], fallos: [] });
  });
});

describe("la puerta de T49", () => {
  const when = new Date("2026-09-23T14:05:09Z");
  const sana = record({ caso: "sana", novel: NOVEL, date: when, commit: "c", checks: coverChecks(manifest(), cover()), evidence: [] });
  const rota = record({
    caso: "sin-dedicatoria",
    novel: NOVEL,
    date: when,
    commit: "c",
    checks: coverChecks(manifest({ dedication: "" }), cover({ dedication: null })),
    evidence: [],
  });

  it("pasa cuando la copia sana pasa y la copia sin dedicatoria falla por la dedicatoria, al backend", () => {
    expect(gateOutcome(sana, rota).ok).toBe(true);
  });

  it("no pasa si la copia sana falla, ni si la rota pasa o falla por otra cosa o a otro rol", () => {
    expect(gateOutcome(rota, rota).ok).toBe(false);
    expect(gateOutcome(sana, sana).ok).toBe(false);
    const otra = record({
      caso: "sin-dedicatoria",
      novel: NOVEL,
      date: when,
      commit: "c",
      checks: coverChecks(manifest(), cover({ dedication: null })),
      evidence: [],
    });
    expect(gateOutcome(sana, otra).ok).toBe(false);
  });
});
