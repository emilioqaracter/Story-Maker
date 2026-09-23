import { describe, expect, it } from "vitest";

import {
  lastVersion,
  readingPosition,
  rememberNovel,
  saveLastVersion,
  saveReadingPosition,
  storedKeys,
  visitedNovels,
} from "./local";

describe("lo que guarda el navegador (RD-29)", () => {
  it("solo identificadores, posicion por novela y version, y ultima version", () => {
    rememberNovel("prueba-uno");
    rememberNovel("prueba-dos");
    rememberNovel("prueba-uno");
    saveReadingPosition("prueba-uno", 1, { chapter: 3 });
    saveLastVersion("prueba-uno", 2);

    expect(visitedNovels()).toEqual(["prueba-uno", "prueba-dos"]);
    expect(readingPosition("prueba-uno", 1)).toEqual({ chapter: 3 });
    expect(readingPosition("prueba-uno", 2)).toBeUndefined();
    expect(lastVersion("prueba-uno")).toBe(2);
    expect(storedKeys().sort()).toEqual([
      "story-maker:novels",
      "story-maker:position:prueba-uno:1",
      "story-maker:version:prueba-uno",
    ]);
    for (const key of storedKeys()) {
      const raw = globalThis.localStorage.getItem(key) ?? "";
      expect(raw.length).toBeLessThan(600);
    }
  });

  it("no guarda lo que no es un identificador, y lo que lee lo valida", () => {
    rememberNovel("<script>");
    rememberNovel("Capítulo entero de prosa con espacios");
    expect(visitedNovels()).toEqual([]);
    globalThis.localStorage.setItem("story-maker:novels", '["valida-uno", 42, "<b>"]');
    globalThis.localStorage.setItem("story-maker:position:valida-uno:1", '{"chapter": "tres"}');
    expect(visitedNovels()).toEqual(["valida-uno"]);
    expect(readingPosition("valida-uno", 1)).toBeUndefined();
  });
});
