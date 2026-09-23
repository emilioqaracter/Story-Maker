#!/usr/bin/env node
/* eslint-disable local/boundaries -- Guion de desarrollo, no aplicacion: arranca procesos con los modulos de Node y
   conduce el navegador con Playwright. La lista cerrada de RNF-41 es la de la aplicacion y sus pruebas; este fichero
   no lo importa nadie ni lo monta ninguna ruta (architecture.md §2.3, visual/). */
/* global fetch, setTimeout -- los de Node, que la configuracion de eslint no declara para .mjs */
// La validacion visual repetible (`specs/srs-backend-v4.md` RF-267, RI-69, D-96; tramo T49).
//
// Siembra una novela congelada con brief de prueba (`seed.py`), hace dos copias
// —una sana y otra sin dedicatoria—, levanta el backend sobre ellas con el
// frontend construido montado en `/app/` (como en produccion, D-67), abre
// Chromium sin cabeza y recorre portada, indice, cada capitulo por la
// navegacion y la ficha de personajes y lugares. Cada comprobacion contrasta lo
// que pinta la pagina con lo que sirve la API, y `verdict.ts` decide a que rol
// vuelve cada fallo: dato que falta, backend; dato servido y no pintado,
// frontend. Nunca reabre un capitulo.
//
// Deja en `visual/results/` un registro fechado por caso (JSON) y sus capturas.
// Las capturas son evidencia, no oraculo: el veredicto sale de los selectores.
//
//     npm run visual                     # construye el sitio y ejecuta la puerta de T49
//     node visual/tour.mjs               # la puerta: la sana pasa y la sin dedicatoria falla, al backend
//     node visual/tour.mjs --caso sana   # un solo caso; sale con 1 si el recorrido falla
//     node visual/tour.mjs --novela f.sqlite   # sobre una copia de otra novela en vez de la sembrada
//     node visual/tour.mjs --serve       # solo levanta el backend sobre las copias, para el MCP de .mcp.json
//
// Nunca abre `backend/runs-golden/` ni `backend/runs-real/` salvo que se le pase
// con `--novela`, y aun entonces trabaja sobre una copia en un directorio temporal.

import { spawn, spawnSync } from "node:child_process";
import { copyFileSync, existsSync, mkdirSync, mkdtempSync, openSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { chromium } from "playwright";

import { bibleChecks, chapterCheck, chapterOf, coverChecks, gateOutcome, judge, record, resultName, tocCheck } from "./verdict.ts";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, "..");
const BACKEND = path.resolve(FRONTEND, "..", "backend");
const DIST = path.join(FRONTEND, "dist", "index.html");
const RESULTS = path.join(HERE, "results");
const SEED = path.join(HERE, "seed.py");
const PYTHON = process.env.PYTHON ?? (process.platform === "win32" ? "python" : "python3");

/** Los dos casos de la puerta de T49, cada uno con su novela en el mismo directorio de tiradas. */
const CASES = [
  { caso: "sana", novel: "novela-visual", strip: false },
  { caso: "sin-dedicatoria", novel: "novela-sin-dedicatoria", strip: true },
];

const TIMEOUT = 15_000;

function args(argv) {
  const out = { caso: null, novela: null, serve: false, port: 0 };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    if (a === "--caso") out.caso = argv[++i] ?? "";
    else if (a === "--novela") out.novela = argv[++i] ?? "";
    else if (a === "--serve") out.serve = true;
    else if (a === "--port") out.port = Number(argv[++i]);
    else throw new Error(`argumento desconocido: ${a}`);
  }
  if (out.caso !== null && !CASES.some((c) => c.caso === out.caso)) {
    throw new Error(`--caso es ${CASES.map((c) => c.caso).join(" o ")}`);
  }
  return out;
}

function python(...argv) {
  const r = spawnSync(PYTHON, [SEED, ...argv], {
    encoding: "utf-8",
    env: { ...process.env, PYTHONIOENCODING: "utf-8" },
  });
  if (r.status !== 0) throw new Error(`seed.py ${argv[0]} fallo:\n${r.stderr || r.error}`);
  return r.stdout;
}

/** El directorio de tiradas temporal con una copia por caso. El original no se toca nunca. */
function prepareRuns(novela) {
  const runs = mkdtempSync(path.join(tmpdir(), "story-maker-visual-"));
  const base = path.join(runs, "base.sqlite");
  if (novela) copyFileSync(path.resolve(novela), base);
  else python("create", base);
  for (const c of CASES) {
    const copy = path.join(runs, `${c.novel}.sqlite`);
    copyFileSync(base, copy);
    if (c.strip) python("strip-dedication", copy);
  }
  rmSync(base);
  return runs;
}

function freePort() {
  return new Promise((resolve, reject) => {
    const s = createServer();
    s.once("error", reject);
    s.listen(0, "127.0.0.1", () => {
      const { port } = s.address();
      s.close(() => resolve(port));
    });
  });
}

/** El backend sobre el directorio temporal, sin Langfuse: ninguna prueba habla con un servicio real (RNF-53). */
async function startBackend(runs, wanted) {
  const port = wanted || (await freePort());
  const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !/^(LANGFUSE_|OTEL_)/i.test(k)));
  const log = path.join(runs, "backend.log");
  const fd = openSync(log, "w");
  const child = spawn(PYTHON, ["-m", "uvicorn", "orchestration.app:app", "--host", "127.0.0.1", "--port", String(port)], {
    cwd: BACKEND,
    env: { ...env, STORY_MAKER_RUNS: runs, PYTHONUNBUFFERED: "1" },
    stdio: ["ignore", fd, fd],
  });
  const base = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 90_000;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) break;
    try {
      const r = await fetch(`${base}/app/`);
      if (r.ok) return { child, base };
    } catch {
      // aun arrancando
    }
    await new Promise((r) => setTimeout(r, 500));
  }
  child.kill();
  throw new Error(`el backend no arranco en ${base}:\n${readFileSync(log, "utf-8").slice(-2000)}`);
}

async function api(base, route) {
  try {
    const r = await fetch(`${base}${route}`);
    return { ok: r.ok, status: r.status, body: r.ok ? await r.json() : null };
  } catch (e) {
    return { ok: false, status: 0, body: null, error: String(e) };
  }
}

const text = async (locator) => ((await locator.count()) > 0 ? await locator.first().textContent() : null);

/** Lo que la API sirve de la novela, que es el oraculo de los datos. */
async function served(base, novel) {
  const versions = await api(base, `/novels/${novel}/versions`);
  const version = versions.ok ? (versions.body.versions.find((v) => v.current)?.number ?? 1) : 1;
  const [state, manifest, entities] = await Promise.all([
    api(base, `/novels/${novel}`),
    api(base, `/novels/${novel}/versions/${version}`),
    api(base, `/novels/${novel}/entities`),
  ]);
  const m = manifest.ok
    ? { ...manifest.body, chapters: manifest.body.chapters.map((c) => c.number) }
    : { title: "", dedication: "", recipient_name: "", chapters: [] };
  const all = entities.ok ? entities.body.entities : [];
  const people = all.filter((e) => e.kind === "person");
  const person = people.find((e) => e.name === m.recipient_name) ?? people[0];
  const place = all.find((e) => e.kind === "place");
  const card = person ? await api(base, `/novels/${novel}/entities/${person.entity_id}`) : { ok: false, body: null };
  const scenes = {};
  for (const n of m.chapters) {
    const c = await api(base, `/novels/${novel}/versions/${version}/chapters/${n}`);
    scenes[n] = c.ok ? c.body.scenes.length : 0;
  }
  return {
    version,
    frozen: state.ok ? state.body.frozen_chapters : -1,
    manifest: m,
    person: { name: person?.name ?? "", chapters: card.ok ? card.body.appearances.map((a) => a.chapter) : [] },
    place: { name: place?.name ?? "" },
    scenes,
  };
}

async function shot(page, dir, name, evidence) {
  const file = path.join(dir, `${name}.png`);
  await page.screenshot({ path: file, fullPage: true });
  evidence.push(path.relative(FRONTEND, file).split(path.sep).join("/"));
}

/** El recorrido de un caso: portada, indice, capitulos por la navegacion, ficha. */
async function tour(browser, base, c, date) {
  const name = resultName(date, c.caso);
  const dir = path.join(RESULTS, name);
  mkdirSync(dir, { recursive: true });
  const evidence = [];
  const checks = [];
  const data = await served(base, c.novel);
  const context = await browser.newContext({ viewport: { width: 1100, height: 900 }, locale: "es-ES" });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(m.text());
  });
  page.setDefaultTimeout(TIMEOUT);

  try {
    // Portada e indice.
    await page.goto(`${base}/app/novels/${c.novel}`);
    await page.locator("article.cover, [role=alert]").first().waitFor();
    const header = page.locator("article.cover .cover-header");
    checks.push(
      ...coverChecks(data.manifest, {
        title: await text(header.locator("h1")),
        dedication: await text(header.locator(".dedication")),
        hint: await text(header.locator("p.hint", { hasText: "Una novela para" })),
      }),
    );
    const links = await page
      .locator("article.cover section.toc ol > li > a")
      .evaluateAll((as) => as.map((a) => ({ text: a.textContent ?? "", href: a.getAttribute("href") ?? "" })));
    checks.push(tocCheck(c.novel, data.version, data.manifest, data.frozen, links));
    await shot(page, dir, "portada", evidence);

    // Cada capitulo: el primero desde el indice, los demas por «Capítulo n →».
    const numbers = [...data.manifest.chapters].sort((a, b) => a - b);
    const missingNext = [];
    for (const [i, n] of numbers.entries()) {
      if (i === 0) {
        const first = page.locator("section.toc ol > li > a").first();
        if ((await first.count()) > 0) await first.click();
        else await page.goto(`${base}/app/novels/${c.novel}/v/${data.version}/chapters/${n}`);
      } else {
        const next = page.locator("nav.chapter-nav a", { hasText: `Capítulo ${n} →` });
        if ((await next.count()) > 0) await next.click();
        else {
          missingNext.push(n);
          await page.goto(`${base}/app/novels/${c.novel}/v/${data.version}/chapters/${n}`);
        }
      }
      const heading = page.locator("article.chapter h2");
      await heading.filter({ hasText: `Capítulo ${n}` }).first().waitFor().catch(() => undefined);
      const scenes = await page
        .locator("article.chapter section.scene")
        .evaluateAll((ss) => ss.map((s) => (s.textContent ?? "").replace(s.querySelector("h3")?.textContent ?? "", "").trim()));
      checks.push(chapterCheck(n, data.scenes[n] ?? 0, { heading: await text(heading), scenes: scenes.length, empty: scenes.filter((t) => t === "").length }));
      if (i === 0) await shot(page, dir, `capitulo-${n}`, evidence);
    }
    checks.push(
      judge(
        "navegacion",
        "Se pasa de un capítulo al siguiente con la navegación",
        { ok: true, detail: "" },
        { ok: missingNext.length === 0, detail: `falta el enlace «Capítulo n →» hacia [${missingNext.join(", ")}]` },
      ),
    );

    // Vuelta al indice y ficha de personajes y lugares.
    const back = page.locator("nav.chapter-nav a", { hasText: "Índice" });
    if ((await back.count()) > 0) await back.click();
    else await page.goto(`${base}/app/novels/${c.novel}`);
    const bibleLink = page.locator(".cover-links a", { hasText: "Personajes y lugares" });
    if ((await bibleLink.count()) > 0) await bibleLink.click();
    else await page.goto(`${base}/app/novels/${c.novel}/bible`);
    await page.locator("section.bible, [role=alert]").first().waitFor();
    const listed = (who) => page.locator("ul.entity-list li > a", { hasText: who }).count();
    const personListed = data.person.name !== "" && (await listed(data.person.name)) > 0;
    await page.getByRole("tab", { name: "Lugares" }).click().catch(() => undefined);
    const placeListed = data.place.name !== "" && (await listed(data.place.name)) > 0;
    await shot(page, dir, "ficha-lugares", evidence);
    await page.getByRole("tab", { name: "Personajes" }).click().catch(() => undefined);
    let heading = null;
    let appearances = [];
    if (personListed) {
      await page.locator("ul.entity-list li > a", { hasText: data.person.name }).first().click();
      await page.locator("article.entity-card h1").waitFor();
      heading = await text(page.locator("article.entity-card h1"));
      appearances = (
        await page
          .locator("article.entity-card h2", { hasText: "Dónde aparece" })
          .locator("xpath=following-sibling::ul[1]//a")
          .evaluateAll((as) => as.map((a) => a.getAttribute("href") ?? ""))
      )
        .map(chapterOf)
        .filter((n) => n !== null);
      await shot(page, dir, "ficha-personaje", evidence);
    }
    checks.push(...bibleChecks({ person: data.person, place: data.place }, { personListed, placeListed, heading, appearances }));
  } catch (e) {
    // Una pagina que no llega a pintar lo que se espera es un fallo de presentacion, salvo que la API ya fallara.
    const apiOk = data.manifest.title !== "" && data.frozen >= 0;
    checks.push(judge("recorrido", "El recorrido llega al final", { ok: apiOk, detail: "la API no sirve la novela" }, { ok: false, detail: String(e).split("\n")[0] }));
    await shot(page, dir, "fallo", evidence).catch(() => undefined);
  } finally {
    await context.close();
  }
  checks.push(judge("consola", "La página no registra errores", { ok: true, detail: "" }, { ok: errors.length === 0, detail: errors.slice(0, 3).join(" | ") }));

  const r = record({ caso: c.caso, novel: c.novel, date, commit: commit(), checks, evidence });
  const file = path.join(RESULTS, `${name}.json`);
  writeFileSync(file, JSON.stringify(r, null, 2) + "\n", "utf-8");
  return { record: r, file: path.relative(FRONTEND, file).split(path.sep).join("/") };
}

function commit() {
  const head = spawnSync("git", ["rev-parse", "--short", "HEAD"], { cwd: FRONTEND, encoding: "utf-8" });
  const dirty = spawnSync("git", ["status", "--porcelain", "--", ".", ":(exclude)visual/results"], { cwd: FRONTEND, encoding: "utf-8" });
  const sha = head.status === 0 ? head.stdout.trim() : "desconocido";
  return dirty.status === 0 && dirty.stdout.trim() !== "" ? `${sha}+cambios` : sha;
}

function report({ record: r, file }) {
  process.stdout.write(`  ${r.resultado === "pasa" ? "pasa " : "FALLA"} ${r.caso} · ${r.comprobaciones.length} comprobaciones · ${file}\n`);
  for (const f of r.fallos) process.stdout.write(`        ${f.id} → vuelve a ${f.role}: ${f.detail}\n`);
}

async function main() {
  const opts = args(process.argv.slice(2));
  if (!existsSync(DIST)) {
    // Fallo cerrado (AGENTS.md §5.3.6): sin sitio construido no hay nada que mirar.
    process.stderr.write("No hay frontend/dist/: npm run visual construye el sitio antes del recorrido\n");
    return 1;
  }
  const runs = prepareRuns(opts.novela);
  let backend;
  try {
    backend = await startBackend(runs, opts.port);
    if (opts.serve) {
      process.stdout.write(
        `Backend con el frontend en ${backend.base}/app/ sobre copias en ${runs}\n` +
          CASES.map((c) => `  ${c.caso}: ${backend.base}/app/novels/${c.novel}\n`).join("") +
          "Recorrido para el MCP de navegador: portada con titulo, dedicatoria y «Una novela para…»; un enlace del indice por\n" +
          "capitulo congelado; cada capitulo por «Capítulo n →»; «Personajes y lugares», el personaje y su «Dónde aparece».\n" +
          "Ctrl+C para parar.\n",
      );
      await new Promise((resolve) => process.once("SIGINT", resolve));
      return 0;
    }
    const browser = await chromium.launch({ headless: true });
    try {
      const date = new Date();
      const chosen = CASES.filter((c) => opts.caso === null || c.caso === opts.caso);
      const results = [];
      for (const c of chosen) {
        const out = await tour(browser, backend.base, c, date);
        report(out);
        results.push(out.record);
      }
      if (opts.caso !== null) return results[0]?.resultado === "pasa" ? 0 : 1;
      const [sana, rota] = results;
      const gate = gateOutcome(sana, rota);
      process.stdout.write(
        gate.ok
          ? "\nvalidacion visual (T49): en verde · la copia sana pasa y la copia sin dedicatoria falla, al backend\n"
          : `\nvalidacion visual (T49): FALLA · ${gate.detail}\n`,
      );
      return gate.ok ? 0 : 1;
    } finally {
      await browser.close();
    }
  } finally {
    backend?.child.kill();
    await new Promise((r) => setTimeout(r, 300));
    rmSync(runs, { recursive: true, force: true, maxRetries: 10, retryDelay: 200 });
  }
}

main().then(
  (code) => process.exit(code),
  (e) => {
    process.stderr.write(`${e instanceof Error ? e.stack : String(e)}\n`);
    process.exit(1);
  },
);
