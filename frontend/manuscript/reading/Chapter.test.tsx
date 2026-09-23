import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { POLL_MS } from "../../commons/api/poll";
import type { Schemas } from "../../commons/api/client";
import { readingPosition } from "../../commons/storage/local";
import { HOSTILE, NOVEL, novelHandlers, requestHandler, RequestsDouble } from "../../commons/testing/fixtures";
import { renderAt } from "../../commons/testing/render";
import { requests, server } from "../../commons/testing/server";
import { manuscriptRoutes } from "../routes";

afterEach(() => {
  vi.useRealTimers();
});

function twoVersions(): RequestsDouble {
  const r = new RequestsDouble();
  r.create({ text: "el perro se llama Nala", anchor: { kind: "fact", entity_id: "rex", attribute: "nombre" } });
  r.applyAll();
  return r;
}

/** Selecciona texto dentro de la lectura como lo haria el lector con el raton. */
function select(node: Node, from: number, to: number, endNode: Node = node) {
  const selection = document.getSelection();
  if (!selection) throw new Error("sin seleccion");
  selection.removeAllRanges();
  selection.setBaseAndExtent(node, from, endNode, to);
}

describe("lectura de un capitulo en una version (RF-180, RF-181, RF-185)", () => {
  it("pinta las escenas en orden con su identificador, y el texto hostil como texto", async () => {
    server.use(...novelHandlers());
    const { container } = renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/1/chapters/1`);
    expect(await screen.findByRole("heading", { name: "Capítulo 1" })).toBeTruthy();
    const scenes = [...container.querySelectorAll("[data-scene-id]")].map((s) => s.getAttribute("data-scene-id"));
    expect(scenes).toEqual(["c1e1", "c1e2"]);
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain(HOSTILE);
  });

  it("navega al siguiente y al indice, y recuerda la posicion", async () => {
    server.use(...novelHandlers());
    renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/1/chapters/1`);
    const next = await screen.findByRole("link", { name: "Capítulo 2 →" });
    expect(next.getAttribute("href")).toBe(`/novels/${NOVEL}/v/1/chapters/2`);
    expect(screen.queryByRole("link", { name: /← Capítulo/ })).toBeNull();
    expect(readingPosition(NOVEL, 1)).toEqual({ chapter: 1 });
  });

  it("en la version 2 marca la escena cambiada y deja ver la anterior al lado", async () => {
    server.use(...novelHandlers(undefined, twoVersions()));
    const { container } = renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/2/chapters/1`);
    expect(await screen.findByText(/cambiada en esta versión/)).toBeTruthy();
    expect(container.querySelectorAll(".scene.changed")).toHaveLength(1);
    fireEvent.click(await screen.findByRole("button", { name: "Ver la versión anterior al lado" }));
    expect(screen.getByText("Lucía llegó al parque con Rex.")).toBeTruthy();
    expect(screen.getByText("Lucía llegó al parque con Nala.")).toBeTruthy();
  });

  it("leer entero no emite ninguna peticion que no sea GET (RNF-38)", async () => {
    server.use(...novelHandlers());
    renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/1/chapters/2`);
    expect(await screen.findByRole("heading", { name: "Capítulo 2" })).toBeTruthy();
    expect(requests.length).toBeGreaterThan(0);
    expect(requests.every((r) => r.method === "GET")).toBe(true);
  });

  it("un capitulo que no esta en la version es «no existe»", async () => {
    server.use(...novelHandlers());
    renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/1/chapters/7`);
    expect(await screen.findByText(/no esta en la version/)).toBeTruthy();
  });
});

describe("pedir un cambio desde la lectura (RF-187 a RF-190)", () => {
  it("la seleccion viaja como ancla de fragmento con la cita literal", async () => {
    const double = new RequestsDouble();
    const bodies: Schemas["ChangeRequestIn"][] = [];
    server.use(requestHandler(double, (b) => bodies.push(b)), ...novelHandlers(undefined, double));
    const { container } = renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/1/chapters/1`);
    await screen.findByRole("heading", { name: "Capítulo 1" });
    const first = container.querySelector("[data-scene-id='c1e1'] p")?.firstChild;
    if (!first) throw new Error("sin texto");
    select(first, 22, 30);
    fireEvent.mouseUp(container.querySelector("article") as Element);
    fireEvent.click(await screen.findByRole("button", { name: "Pedir un cambio" }));
    fireEvent.change(screen.getByPlaceholderText(/el perro se llama Nala/), { target: { value: "el perro se llama Nala" } });
    fireEvent.click(screen.getByRole("button", { name: "Pedir el cambio" }));

    expect(await screen.findByText(/En cola/)).toBeTruthy();
    expect(screen.getByText(/«Rex» → «Nala»/)).toBeTruthy();
    expect(bodies[0]?.anchor).toEqual({ kind: "fragment", version: 1, chapter: 1, scene_id: "c1e1", quote: "con Rex." });
  });

  it("una seleccion que cruza dos escenas no ancla", async () => {
    server.use(...novelHandlers());
    const { container } = renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/1/chapters/1`);
    await screen.findByRole("heading", { name: "Capítulo 1" });
    const a = container.querySelector("[data-scene-id='c1e1'] p")?.firstChild;
    const b = container.querySelector("[data-scene-id='c1e2'] p")?.firstChild;
    if (!a || !b) throw new Error("sin texto");
    select(a, 3, 4, b);
    fireEvent.mouseUp(container.querySelector("article") as Element);
    expect(screen.queryByRole("button", { name: "Pedir un cambio" })).toBeNull();
  });

  it("una peticion que no se entiende vuelve rechazada con su motivo y deja reformular", async () => {
    const double = new RequestsDouble();
    server.use(requestHandler(double), ...novelHandlers(undefined, double));
    const { container } = renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/1/chapters/1`);
    await screen.findByRole("heading", { name: "Capítulo 1" });
    const first = container.querySelector("[data-scene-id='c1e1'] p")?.firstChild;
    if (!first) throw new Error("sin texto");
    select(first, 0, 5);
    fireEvent.mouseUp(container.querySelector("article") as Element);
    fireEvent.click(await screen.findByRole("button", { name: "Pedir un cambio" }));
    fireEvent.change(screen.getByPlaceholderText(/el perro se llama Nala/), { target: { value: "cámbialo" } });
    fireEvent.click(screen.getByRole("button", { name: "Pedir el cambio" }));
    expect(await screen.findByText(/No se aplicará: La petición es ambigua/)).toBeTruthy();
    expect(screen.getByText("Reformula la petición")).toBeTruthy();
  });

  it("al aplicarse anuncia la version nueva con sus capitulos y la lectura no se mueve", async () => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const double = new RequestsDouble();
    server.use(requestHandler(double), ...novelHandlers(undefined, double));
    const { container, router } = renderAt(manuscriptRoutes, `/novels/${NOVEL}/v/1/chapters/1`);
    await vi.waitFor(() => expect(screen.getByRole("heading", { name: "Capítulo 1" })).toBeTruthy());
    const first = container.querySelector("[data-scene-id='c1e1'] p")?.firstChild;
    if (!first) throw new Error("sin texto");
    select(first, 22, 30);
    fireEvent.mouseUp(container.querySelector("article") as Element);
    fireEvent.click(screen.getByRole("button", { name: "Pedir un cambio" }));
    fireEvent.change(screen.getByPlaceholderText(/el perro se llama Nala/), { target: { value: "el perro se llama Nala" } });
    fireEvent.click(screen.getByRole("button", { name: "Pedir el cambio" }));
    await vi.waitFor(() => expect(screen.getByText(/En cola/)).toBeTruthy());

    double.applyAll();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(POLL_MS);
    });
    await vi.waitFor(() => expect(screen.getByText(/versión 2 lista, cambiaron los capítulos 1/)).toBeTruthy());
    expect(screen.getByRole("link", { name: "Leer el capítulo 1 en la versión 2" }).getAttribute("href")).toBe(
      `/novels/${NOVEL}/v/2/chapters/1`,
    );
    expect(router.state.location.pathname).toBe(`/novels/${NOVEL}/v/1/chapters/1`);
    expect(container.textContent).toContain("Lucía llegó al parque con Rex.");
  });
});
