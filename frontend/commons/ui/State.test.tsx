import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Empty, Loading } from "./State";

describe("estados compartidos", () => {
  it("la carga se anuncia como estado, sin interrumpir", () => {
    render(<Loading>Cargando la novela…</Loading>);
    const status = screen.getByRole("status");
    expect(status.textContent).toBe("Cargando la novela…");
    expect(status.getAttribute("aria-live")).toBe("polite");
  });

  it("un vacio lleva su explicacion y, si la hay, su salida", () => {
    render(<Empty action={<a href="/new">Encargar una</a>}>Todavía no hay ninguna novela.</Empty>);
    expect(screen.getByText("Todavía no hay ninguna novela.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Encargar una" })).toBeTruthy();
  });
});
