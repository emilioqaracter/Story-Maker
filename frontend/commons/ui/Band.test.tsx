import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { illustration } from "../brand/art";
import { Home } from "../shell/Home";
import { novelHandlers } from "../testing/fixtures";
import { server } from "../testing/server";
import { Band } from "./Band";
import { CoverArt } from "./CoverArt";

describe("banda y portada en plano (srs-frontend-v2 RF-277, RF-280)", () => {
  it("la banda pinta rotulo y titulo; la ilustracion, si existe, es decorativa, y si no, queda el degradado", () => {
    const { container } = render(
      <Band art="hero-estadio" eyebrow="Épica deportiva" title="Novelas">
        <p>Entradilla</p>
      </Band>,
    );
    expect(screen.getByRole("heading", { level: 1, name: "Novelas" })).toBeTruthy();
    expect(screen.getByText("Épica deportiva")).toBeTruthy();
    const img = container.querySelector("img");
    if (illustration("hero-estadio")) {
      expect(img?.getAttribute("alt")).toBe("");
    } else {
      expect(img).toBeNull();
      expect(container.querySelector(".band-plain")).toBeTruthy();
    }
  });

  it("la portada en plano no la anuncia un lector de pantalla: el nombre lo da quien la monta", () => {
    const { container } = render(<CoverArt novel="real" title="El nueve" recipient="Ana" />);
    expect(container.firstElementChild?.getAttribute("aria-hidden")).toBe("true");
    expect(container.textContent).toBe("El nuevePara Ana");
  });

  it("cada novela de la lista lleva su portada en miniatura, y la tarjeta sigue teniendo un solo enlace", async () => {
    server.use(...novelHandlers());
    const { container } = render(
      <MemoryRouter>
        <Home />
      </MemoryRouter>,
    );
    const link = await screen.findByRole("link", { name: "El verano de Rex" });
    const card = link.closest("li");
    expect(card?.querySelector(".cover-art")).toBeTruthy();
    expect(card?.querySelectorAll("a")).toHaveLength(1);
    expect(container.querySelector(".band h1")?.textContent).toBe("Novelas");
  });
});
