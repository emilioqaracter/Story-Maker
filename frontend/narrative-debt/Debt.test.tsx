import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NOVEL, novelHandlers } from "../commons/testing/fixtures";
import { notFound, onGet, server } from "../commons/testing/server";
import { Debt } from "./Debt";

describe("deuda narrativa (RF-197)", () => {
  it("lista los setups abiertos de RI-07 con su estado, sin calcular nada", async () => {
    server.use(...novelHandlers());
    render(<Debt novel={NOVEL} />);
    expect(await screen.findByText("La lesión de rodilla de Marcos")).toBeTruthy();
    expect(screen.getByText(/1 setups abiertos sin payoff · 0 previstos sin plantar · 0 cobrados/)).toBeTruthy();
    expect(screen.getByText(/plantado en el capítulo 1, escena 1.1/)).toBeTruthy();
  });

  it("sin escaleta congelada, dice lo que dice el backend", async () => {
    server.use(onGet("/novels/{novel_id}/debt", () => notFound("la novela no tiene escaleta congelada todavia")));
    render(<Debt novel={NOVEL} />);
    expect(await screen.findByText("la novela no tiene escaleta congelada todavia")).toBeTruthy();
  });
});
