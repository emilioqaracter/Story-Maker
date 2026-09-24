import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Schemas } from "../commons/api/client";
import { NOVEL, novelHandlers, requestHandler, RequestsDouble } from "../commons/testing/fixtures";
import { renderAt } from "../commons/testing/render";
import { server } from "../commons/testing/server";
import { storyBibleRoutes } from "./routes";
import { tabAfterKey, visibleTabs } from "./EntityList";

describe("ficha de personajes y lugares (RF-192 a RF-195)", () => {
  it("lista personajes y lugares con sus capitulos enlazados a la version vigente", async () => {
    server.use(...novelHandlers());
    renderAt(storyBibleRoutes, `/novels/${NOVEL}/bible`);
    const lucia = await screen.findByRole("link", { name: "Lucía" });
    expect(lucia.getAttribute("href")).toBe(`/novels/${NOVEL}/bible/lucia`);
    expect(screen.getByText(/también Lu/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "2" }).getAttribute("href")).toBe(`/novels/${NOVEL}/v/1/chapters/2`);
    expect(screen.getByText(/canon vigente/)).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Lugares" }));
    expect(screen.getByRole("link", { name: "El parque" })).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Objetos" })).toBeTruthy();
    expect(screen.queryByRole("tab", { name: "Instituciones" })).toBeNull();
  });

  it("la ficha lleva hechos con procedencia, relaciones con vigencia y apariciones enlazadas a su escena", async () => {
    server.use(...novelHandlers());
    renderAt(storyBibleRoutes, `/novels/${NOVEL}/bible/lucia`);
    expect(await screen.findByRole("heading", { name: "Lucía" })).toBeTruthy();
    expect(screen.getByText("del encargo")).toBeTruthy();
    expect(screen.getByText(/desde 2026-08-01/)).toBeTruthy();
    const escena = screen.getByRole("link", { name: "Capítulo 1, escena 1" });
    expect(escena.getAttribute("href")).toBe(`/novels/${NOVEL}/v/1/chapters/1#scene-c1e1`);
  });

  it("pedir un cambio sobre un hecho envia el ancla de hecho", async () => {
    const double = new RequestsDouble();
    const bodies: Schemas["ChangeRequestIn"][] = [];
    server.use(requestHandler(double, (b) => bodies.push(b)), ...novelHandlers(undefined, double));
    renderAt(storyBibleRoutes, `/novels/${NOVEL}/bible/lucia`);
    await screen.findByRole("heading", { name: "Lucía" });
    fireEvent.click(screen.getAllByRole("button", { name: "Pedir un cambio" })[0] as HTMLElement);
    fireEvent.change(screen.getByPlaceholderText(/el perro se llama Nala/), { target: { value: "se llama Nala" } });
    fireEvent.click(screen.getByRole("button", { name: "Pedir el cambio" }));
    expect(await screen.findByText(/En cola/)).toBeTruthy();
    expect(bodies[0]?.anchor).toEqual({ kind: "fact", entity_id: "lucia", attribute: "nombre" });
  });

  it("una entidad que no existe es «no existe»", async () => {
    server.use(...novelHandlers());
    renderAt(storyBibleRoutes, `/novels/${NOVEL}/bible/nadie`);
    expect(await screen.findByRole("heading", { name: "No existe" })).toBeTruthy();
  });

  it("las pestanas de instituciones y objetos solo salen si los hay", () => {
    expect(visibleTabs([{ kind: "person" }]).map((t) => t.kind)).toEqual(["person", "place"]);
    expect(visibleTabs([{ kind: "institution" }]).map((t) => t.kind)).toEqual(["person", "place", "institution"]);
  });

  it("las flechas, Inicio y Fin mueven entre pestanas dando la vuelta; otra tecla no", () => {
    expect(tabAfterKey("ArrowRight", 0, 3)).toBe(1);
    expect(tabAfterKey("ArrowRight", 2, 3)).toBe(0);
    expect(tabAfterKey("ArrowLeft", 0, 3)).toBe(2);
    expect(tabAfterKey("Home", 2, 3)).toBe(0);
    expect(tabAfterKey("End", 0, 3)).toBe(2);
    expect(tabAfterKey("a", 0, 3)).toBeNull();
    expect(tabAfterKey("ArrowRight", 0, 0)).toBeNull();
  });

  it("las pestanas se recorren con el teclado: una sola parada de tabulador y el foco sigue a la seleccionada", async () => {
    server.use(...novelHandlers());
    renderAt(storyBibleRoutes, `/novels/${NOVEL}/bible`);
    const personajes = await screen.findByRole("tab", { name: "Personajes" });
    expect(personajes.getAttribute("tabindex")).toBe("0");
    expect(screen.getByRole("tab", { name: "Lugares" }).getAttribute("tabindex")).toBe("-1");
    personajes.focus();
    fireEvent.keyDown(personajes, { key: "ArrowRight" });
    const lugares = screen.getByRole("tab", { name: "Lugares" });
    expect(lugares.getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(lugares);
    expect(screen.getByRole("tabpanel").getAttribute("aria-labelledby")).toBe(lugares.id);
    expect(screen.getByRole("link", { name: "El parque" })).toBeTruthy();
    fireEvent.keyDown(lugares, { key: "End" });
    expect(screen.getByRole("tab", { name: "Objetos" }).getAttribute("aria-selected")).toBe("true");
  });
});
