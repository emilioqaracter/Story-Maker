import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { NOVEL, novelHandlers, WORLD } from "../commons/testing/fixtures";
import { onGet, server } from "../commons/testing/server";
import { Graph, kindGroup, lastInstant } from "./Graph";

function draw() {
  return render(
    <MemoryRouter>
      <Graph novel={NOVEL} />
    </MemoryRouter>,
  );
}

describe("grafo de entidades (RF-196)", () => {
  it("pide RI-06 en el instante del ultimo capitulo congelado", async () => {
    let asked: URL | undefined;
    server.use(
      onGet("/novels/{novel_id}/state", (c) => {
        asked = c.url;
        return WORLD;
      }),
      ...novelHandlers(),
    );
    draw();
    await screen.findByRole("img", { name: "Grafo de entidades" });
    expect(asked?.searchParams.get("at")).toBe("2026-08-21");
    expect(asked?.searchParams.get("seq")).toBe("0");
  });

  it("dibuja las relaciones con su tipo y vigencia, y cada nodo enlaza a su ficha", async () => {
    server.use(...novelHandlers());
    const { container } = draw();
    await screen.findByRole("img", { name: "Grafo de entidades" });
    expect(container.querySelectorAll("svg line")).toHaveLength(1);
    expect(screen.getAllByText("hermano_de").length).toBeGreaterThan(0);
    expect(screen.getByText("desde 2026-01-01")).toBeTruthy();
    const hrefs = [...container.querySelectorAll("svg a")].map((a) => a.getAttribute("href"));
    expect(hrefs.sort()).toEqual([`/novels/${NOVEL}/bible/elena`, `/novels/${NOVEL}/bible/marcos`]);
    expect(container.querySelector("svg i")).toBeNull();
  });

  it("sin capitulos congelados, no hay instante y lo dice", async () => {
    server.use(onGet("/novels/{novel_id}/chapters", () => ({ chapters: [] })), ...novelHandlers());
    draw();
    expect(await screen.findByText(/no hay instante del que dibujar/)).toBeTruthy();
  });

  it("el ultimo instante es el del capitulo de numero mayor", () => {
    expect(
      lastInstant([
        { chapter: 2, scenes: 1, words: 1, ends_at: "2026-02-01", ends_seq: 3 },
        { chapter: 1, scenes: 1, words: 1, ends_at: "2026-01-01", ends_seq: 0 },
      ]),
    ).toEqual({ at: "2026-02-01", seq: 3 });
    expect(lastInstant([])).toBeNull();
  });
});

describe("grafo en 3D (srs-frontend-v2 RF-282, RNF-61)", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  function reducedMotion(reduce: boolean) {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: reduce && query.includes("reduce"), media: query }));
  }

  it("las flechas del teclado giran la figura, y no hay ni un boton ni un formulario", async () => {
    server.use(...novelHandlers());
    const { container } = draw();
    await screen.findByRole("img", { name: "Grafo de entidades" });
    const line = () => container.querySelector("svg line")?.getAttribute("x1");
    const before = line();
    fireEvent.keyDown(container.querySelector(".graph-stage") as Element, { key: "ArrowRight" });
    expect(line()).not.toBe(before);
    expect(container.querySelectorAll("button, form, input")).toHaveLength(0);
    expect(screen.getByText(/flechas del teclado/)).toBeTruthy();
    expect(screen.getByRole("list", { name: "Leyenda" }).textContent).toBe("Personajes");
  });

  it("con movimiento reducido no gira solo", async () => {
    reducedMotion(true);
    const frame = vi.fn(() => 1);
    vi.stubGlobal("requestAnimationFrame", frame);
    server.use(...novelHandlers());
    draw();
    await screen.findByRole("img", { name: "Grafo de entidades" });
    expect(frame).not.toHaveBeenCalled();
  });

  it("sin esa preferencia gira despacio hasta que se toca", async () => {
    reducedMotion(false);
    const frame = vi.fn(() => 1);
    vi.stubGlobal("requestAnimationFrame", frame);
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    server.use(...novelHandlers());
    draw();
    await screen.findByRole("img", { name: "Grafo de entidades" });
    expect(frame).toHaveBeenCalled();
  });

  it("agrupa los tipos libres del canon en personajes, lugares y otras", () => {
    expect(kindGroup("person")).toBe("person");
    expect(kindGroup("Character")).toBe("person");
    expect(kindGroup("place")).toBe("place");
    expect(kindGroup("institution")).toBe("other");
  });
});
