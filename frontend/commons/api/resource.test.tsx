import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { NOVEL, novelHandlers } from "../testing/fixtures";
import { requests, server } from "../testing/server";
import { cacheKey } from "./cache";
import { api } from "./client";
import { settle } from "./errors";
import { useResource } from "./resource";

function Chapters({ label }: { label: string }) {
  const r = useResource(cacheKey(NOVEL, 1, "chapters"), () =>
    settle(() => api.GET("/novels/{novel_id}/chapters", { params: { path: { novel_id: NOVEL } } })),
  );
  return <p>{r.state === "ok" ? `${label}: ${r.data.chapters.length}` : `${label}: ${r.state}`}</p>;
}

describe("respuestas cacheadas (RD-28)", () => {
  it("dos lecturas de la misma version devuelven lo mismo sin volver a pedirlo", async () => {
    server.use(...novelHandlers());
    const first = render(<Chapters label="primera" />);
    expect(await screen.findByText("primera: 2")).toBeTruthy();
    first.unmount();
    render(<Chapters label="segunda" />);
    expect(await screen.findByText("segunda: 2")).toBeTruthy();
    expect(requests.filter((r) => r.path.endsWith("/chapters"))).toHaveLength(1);
  });
});
