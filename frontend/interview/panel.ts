import type { Schemas } from "../commons/api/client";

export type Draft = Schemas["Draft"];
export type FieldName = Schemas["FieldEdit"]["field"];

/**
 * Los campos del panel del brief (RF-169), en el orden de la entrevista. Solo
 * etiquetas y como se leen del borrador: que es obligatorio, que falta y que se
 * contradice lo dice el backend (D-51).
 */
export const PANEL: readonly { field: FieldName; label: string; list?: boolean; long?: boolean }[] = [
  { field: "title", label: "Título" },
  { field: "recipient.name", label: "Destinatario" },
  { field: "recipient.age", label: "Edad" },
  { field: "recipient.birth_date", label: "Fecha de nacimiento" },
  { field: "recipient.role", label: "Papel en la historia" },
  { field: "recipient.traits", label: "Rasgos", list: true },
  { field: "recipient.memories", label: "Recuerdos", list: true },
  { field: "premise", label: "Premisa", long: true },
  { field: "genre", label: "Género" },
  { field: "tone", label: "Tono" },
  { field: "target_words", label: "Extensión en palabras" },
  { field: "start", label: "Arranca el" },
  { field: "dedication", label: "Dedicatoria", long: true },
  { field: "forbidden_words", label: "Palabras que no deben aparecer", list: true },
  { field: "forbidden_themes", label: "Temas que no deben tocarse", list: true },
];

/** El valor de un campo del borrador como texto editable; las listas, separadas por comas. Pura. */
export function shown(draft: Draft, field: FieldName): string {
  const value: unknown = {
    title: draft.title,
    "recipient.name": draft.recipient_name,
    "recipient.age": draft.recipient_age,
    "recipient.birth_date": draft.recipient_birth_date,
    "recipient.role": draft.recipient_role,
    "recipient.traits": draft.recipient_traits,
    "recipient.memories": draft.recipient_memories,
    premise: draft.premise,
    genre: draft.genre,
    tone: draft.tone,
    target_words: draft.target_words,
    start: draft.start,
    dedication: draft.dedication,
    forbidden_words: draft.forbidden_words,
    forbidden_themes: draft.forbidden_themes,
  }[field];
  if (value === null || value === undefined) return "";
  if (Array.isArray(value)) return value.join(", ");
  return String(value);
}

export function fieldId(field: FieldName): string {
  return `field-${field.replace(/\./g, "-")}`;
}
