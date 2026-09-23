import { fireEvent, screen, waitFor } from "@testing-library/react";
import { HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import type { Schemas } from "../commons/api/client";
import { visitedInterviews } from "../commons/storage/local";
import { HOSTILE, NOVEL } from "../commons/testing/fixtures";
import { renderAt } from "../commons/testing/render";
import { onGet, onPost, requests, server } from "../commons/testing/server";
import { interviewRoutes } from "./routes";

type State = Schemas["InterviewState"];
type Turn = Schemas["TurnIn"];

const IID = "abcdef012345";
const ORDER = ["title", "recipient.name", "recipient.age", "recipient.role", "premise", "genre", "tone", "target_words", "start", "dedication"] as const;
const ATTR: Record<string, keyof Schemas["Draft"]> = {
  title: "title",
  "recipient.name": "recipient_name",
  "recipient.age": "recipient_age",
  "recipient.role": "recipient_role",
  premise: "premise",
  genre: "genre",
  tone: "tone",
  target_words: "target_words",
  start: "start",
  dedication: "dedication",
};

const BRIEF: Schemas["Brief"] = {
  title: "El verano",
  start: { stamp: "2026-08-01", seq: 0 },
  entities: [{ id: "lucia", kind: "person", name: "Lucía" }],
  style_guide: "Premisa: x",
  target_words: 30000,
};

/** Un entrevistador minimo: el que decide que falta es el doble, como lo seria el backend (D-51). */
class InterviewDouble {
  draft: Schemas["Draft"] = {};
  messages: Schemas["Message"][] = [{ role: "interviewer", kind: "note", text: "Vamos a preparar el encargo." }];
  proposed: Schemas["ProposedFact"][] = [];
  genreConflict = false;

  state(): State {
    const missing = ORDER.filter((f) => {
      const v = this.draft[ATTR[f] as keyof Schemas["Draft"]];
      return v === undefined || v === null || v === "";
    });
    const contradictions = this.genreConflict
      ? [{ fields: ["recipient.age", "genre"] as [string, string], rule: "edad-genero", message: "El destinatario tiene 10 años y el género «terror» es para mayores de 12." }]
      : [];
    const complete = missing.length === 0 && contradictions.length === 0;
    const question = missing[0] ? { field: missing[0], text: `Pregunta por ${missing[0]}` } : null;
    return {
      interview_id: IID,
      // Como el backend: la pregunta en curso es el ultimo mensaje del entrevistador.
      messages: question ? [...this.messages, { role: "interviewer", kind: "question", text: question.text }] : this.messages,
      question,
      draft: this.draft,
      missing: missing.map((f) => ({ field: f, label: `Etiqueta de ${f}` })),
      contradictions,
      proposed: this.proposed,
      discarded_quotes: 0,
      complete,
      brief: complete ? BRIEF : null,
      novel_id: complete ? NOVEL : null,
    };
  }

  turn(t: Turn): State {
    const current = this.state().question;
    if (t.answer && current) {
      this.messages.push({ role: "person", kind: "answer", text: t.answer });
      const key = ATTR[current.field] as keyof Schemas["Draft"];
      (this.draft as Record<string, unknown>)[key] = /age|words/.test(current.field) ? Number(t.answer) : t.answer;
    }
    for (const e of t.edits ?? []) {
      const key = ATTR[e.field] as keyof Schemas["Draft"];
      (this.draft as Record<string, unknown>)[key] = e.value.trim();
      this.genreConflict = e.field === "genre" && e.value === "terror";
    }
    if (t.free_text) {
      this.messages.push({ role: "person", kind: "free_text", text: t.free_text });
      this.proposed.push({ fact_id: "p1", target: "recipient.memories", value: "Aprender a nadar", quote: "aprendió a nadar", status: "proposed" });
    }
    for (const id of t.accept ?? []) {
      const p = this.proposed.find((x) => x.fact_id === id);
      if (p) {
        p.status = "accepted";
        this.draft.recipient_memories = [...(this.draft.recipient_memories ?? []), p.value];
      }
    }
    return this.state();
  }
}

function serve(double: InterviewDouble, extra: Parameters<typeof server.use> = []) {
  const turns: Turn[] = [];
  server.use(
    ...extra,
    onPost("/interviews", () => double.state(), true),
    onGet("/interviews/{interview_id}", (c) => (c.params.interview_id === IID ? double.state() : HttpResponse.json({ detail: "no existe" }, { status: 404 }))),
    onPost("/interviews/{interview_id}/turns", ({ body }) => {
      turns.push(body);
      return double.turn(body);
    }),
  );
  return turns;
}

function answerAll(value = (f: string) => (f === "recipient.age" ? "10" : f === "target_words" ? "30000" : `valor ${f}`)) {
  return async (double: InterviewDouble) => {
    for (const f of ORDER) {
      await screen.findByText(`Pregunta por ${f}`);
      fireEvent.change(screen.getByRole("textbox", { name: "Tu respuesta" }), { target: { value: value(f) } });
      fireEvent.click(screen.getByRole("button", { name: "Responder" }));
    }
    await waitFor(() => expect(double.state().complete).toBe(true));
  };
}

describe("la entrevista (RF-167 a RF-176)", () => {
  it("entrar en /new crea una entrevista y lleva a su direccion", async () => {
    const double = new InterviewDouble();
    serve(double);
    const { router } = renderAt(interviewRoutes, "/new");
    await waitFor(() => expect(router.state.location.pathname).toBe(`/interviews/${IID}`));
    expect(requests.filter((r) => r.method === "POST" && r.path === "/interviews")).toHaveLength(1);
    expect(visitedInterviews()).toEqual([IID]);
  });

  it("cada respuesta es un turno, y el panel muestra lo que el backend guardo", async () => {
    const double = new InterviewDouble();
    const turns = serve(double);
    renderAt(interviewRoutes, `/interviews/${IID}`);
    await screen.findByText("Pregunta por title");
    fireEvent.change(screen.getByRole("textbox", { name: "Tu respuesta" }), { target: { value: "El verano" } });
    fireEvent.click(screen.getByRole("button", { name: "Responder" }));
    await screen.findByText("Pregunta por recipient.name");
    expect(turns[0]).toEqual({ answer: "El verano" });
    expect((screen.getByRole("textbox", { name: "Título" }) as HTMLInputElement).value).toBe("El verano");
    expect(screen.getByRole("link", { name: "Etiqueta de recipient.name" }).getAttribute("href")).toBe("#field-recipient-name");
  });

  it("«Crear y escribir» solo con el brief completo; no hay «saltar» ni «crear igual»", async () => {
    const double = new InterviewDouble();
    serve(double);
    renderAt(interviewRoutes, `/interviews/${IID}`);
    const crear = await screen.findByRole("button", { name: "Crear y escribir" });
    expect((crear as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: /saltar|crear igual/i })).toBeNull();
    await answerAll()(double);
    await waitFor(() => expect((screen.getByRole("button", { name: "Crear y escribir" }) as HTMLButtonElement).disabled).toBe(false));
  });

  it("una contradiccion se muestra con sus campos y la regla, y bloquea la creacion", async () => {
    const double = new InterviewDouble();
    serve(double);
    renderAt(interviewRoutes, `/interviews/${IID}`);
    await answerAll()(double);
    const genero = await screen.findByRole("textbox", { name: "Género" });
    fireEvent.change(genero, { target: { value: "terror" } });
    fireEvent.click(screen.getByRole("button", { name: "Guardar" }));
    expect(await screen.findByText(/para mayores de 12/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "genre" }).getAttribute("href")).toBe("#field-genre");
    expect((screen.getByRole("button", { name: "Crear y escribir" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("el texto libre viaja aparte, se muestra como texto y sus hechos solo entran al aceptarlos", async () => {
    const double = new InterviewDouble();
    const turns = serve(double);
    const { container } = renderAt(interviewRoutes, `/interviews/${IID}`);
    await screen.findByText("Pregunta por title");
    fireEvent.change(screen.getByRole("textbox", { name: "Texto libre" }), { target: { value: `aquel verano aprendió a nadar ${HOSTILE}` } });
    fireEvent.click(screen.getByRole("button", { name: "Enviar el texto" }));
    expect(await screen.findByText("«aprendió a nadar»")).toBeTruthy();
    expect(turns[0]?.free_text).toContain("aprendió a nadar");
    expect(turns[0]?.answer).toBeUndefined();
    expect(container.querySelector("script")).toBeNull();
    expect((screen.getByRole("textbox", { name: "Recuerdos" }) as HTMLInputElement).value).toBe("");
    fireEvent.click(screen.getByRole("button", { name: "Aceptar" }));
    await waitFor(() => expect((screen.getByRole("textbox", { name: "Recuerdos" }) as HTMLInputElement).value).toBe("Aprender a nadar"));
    expect(turns[1]).toEqual({ accept: ["p1"] });
  });

  it("crear llama a RI-01 con el brief tal como vino y despues a RI-02, y lleva a la novela", async () => {
    const double = new InterviewDouble();
    const created: unknown[] = [];
    serve(double, [
      onPost(
        "/novels",
        ({ body, url }) => {
          created.push({ body, novel: url.searchParams.get("novel_id") });
          return { novel_id: NOVEL, events_loaded: 3 };
        },
        true,
      ),
      onPost("/novels/{novel_id}/run", () => ({ novel_id: NOVEL, running: true, frozen_chapters: 0, quarantines: 0 })),
    ]);
    const { router } = renderAt(interviewRoutes, `/interviews/${IID}`);
    await answerAll()(double);
    fireEvent.click(await screen.findByRole("button", { name: "Crear y escribir" }));
    await waitFor(() => expect(router.state.location.pathname).toBe(`/novels/${NOVEL}`));
    expect(created).toEqual([{ body: BRIEF, novel: NOVEL }]);
    const orden = requests.filter((r) => r.method === "POST").map((r) => r.path);
    expect(orden.slice(-2)).toEqual(["/novels", `/novels/${NOVEL}/run`]);
  });

  it("si RI-01 rechaza el brief, la lista de lo que falla se muestra", async () => {
    const double = new InterviewDouble();
    serve(double, [
      onPost("/novels", () => HttpResponse.json({ detail: [{ msg: "el brief se contradice: edad" }] }, { status: 422 })),
    ]);
    renderAt(interviewRoutes, `/interviews/${IID}`);
    await answerAll()(double);
    fireEvent.click(await screen.findByRole("button", { name: "Crear y escribir" }));
    expect(await screen.findByText("el brief se contradice: edad")).toBeTruthy();
  });

  it("una entrevista que no existe es «no existe»", async () => {
    serve(new InterviewDouble());
    renderAt(interviewRoutes, "/interviews/000000000000");
    expect(await screen.findByRole("heading", { name: "No existe" })).toBeTruthy();
  });
});
