/-
Cronologia de la novela, exportada del canon por `verification/formal/generate.py`
(`specs/srs-backend-v4.md` RF-243). No se edita: se regenera.

Tiempo: minutos desde 0001-01-01T00:00 (D-87). Cada hecho lleva en `src` la
tabla y la clave de la fila que lo produjo; `pending.` es lo que va a entrar.
-/
import StoryMaker.Invariants

open StoryMaker

namespace Chronology

-- Entidades y lugares, numerados por su identificador ordenado:
--   0 = "estadio"
--   1 = "lucia"
--   2 = "marco"
--   3 = "parque"
--   4 = "rex"
--   5 = "tomas"

/-- Un personaje presente en una escena de `chronology`: entidad, instante, desempate, lugar. -/
def presences : List Presence :=
  [ ⟨1, 1065366720, 0, some 3, "chronology[\"c1e1\", \"lucia\"]"⟩  -- 2026-08-11#0
  , ⟨4, 1065366720, 0, some 3, "chronology[\"c1e1\", \"rex\"]"⟩  -- 2026-08-11#0
  , ⟨5, 1065366720, 0, some 3, "chronology[\"c1e1\", \"tomas\"]"⟩  -- 2026-08-11#0
  , ⟨1, 1065368160, 0, some 0, "chronology[\"c1e2\", \"lucia\"]"⟩  -- 2026-08-12#0
  , ⟨2, 1065368160, 0, some 0, "chronology[\"c1e2\", \"marco\"]"⟩  -- 2026-08-12#0
  , ⟨1, 1065369600, 0, some 3, "chronology[\"c1e3\", \"lucia\"]"⟩  -- 2026-08-13#0
  , ⟨2, 1065369600, 0, some 3, "chronology[\"c1e3\", \"marco\"]"⟩  -- 2026-08-13#0
  , ⟨5, 1065369600, 0, some 3, "chronology[\"c1e3\", \"tomas\"]"⟩  -- 2026-08-13#0
  , ⟨1, 1065381120, 0, some 0, "chronology[\"c2e1\", \"lucia\"]"⟩  -- 2026-08-21#0
  , ⟨2, 1065381120, 0, some 0, "chronology[\"c2e1\", \"marco\"]"⟩  -- 2026-08-21#0
  , ⟨4, 1065381120, 0, some 0, "chronology[\"c2e1\", \"rex\"]"⟩  -- 2026-08-21#0
  , ⟨1, 1065381120, 1, some 3, "chronology[\"c2e2\", \"lucia\"]"⟩  -- 2026-08-21#1
  ]

/-- Nacimientos: declarados con `birth_date`, o derivados de `age` (MET-09). -/
def births : List Birth :=
  [ ⟨1, 1059877440, 1059877440, false, "attribute[\"lucia\", \"birth_date\", \"2026-08-01\"]"⟩  -- declarado
  , ⟨2, 1058515201, 1059040800, true, "attribute[\"marco\", \"age\", \"2026-08-01\"]"⟩  -- derivado de la edad
  ]

/-- Edades declaradas: el intervalo de nacimientos compatible con cada una. -/
def ages : List Age :=
  [ ⟨1, 1059566401, 1060093440, "attribute[\"lucia\", \"age\", \"2026-08-01\"]"⟩  -- edad
  , ⟨2, 1058515201, 1059040800, "attribute[\"marco\", \"age\", \"2026-08-01\"]"⟩  -- edad
  ]

/-- Desde cuando existe cada entidad. -/
def existences : List Existence :=
  [ ⟨0, 1065352320, "entity[\"estadio\"]"⟩  -- creada
  , ⟨1, 1065352320, "entity[\"lucia\"]"⟩  -- creada
  , ⟨2, 1065352320, "entity[\"marco\"]"⟩  -- creada
  , ⟨3, 1065352320, "entity[\"parque\"]"⟩  -- creada
  , ⟨4, 1065352320, "entity[\"rex\"]"⟩  -- creada
  , ⟨5, 1065352320, "entity[\"tomas\"]"⟩  -- creada
  ]

/-- Vigencias de atributos, alias, relaciones y competencias (MET-07). -/
def validities : List Validity :=
  [ ⟨1, 1065352320, none, "attribute[\"lucia\", \"age\", \"2026-08-01\"]"⟩  -- vigencia
  , ⟨1, 1065352320, none, "attribute[\"lucia\", \"birth_date\", \"2026-08-01\"]"⟩  -- vigencia
  , ⟨2, 1065352320, none, "attribute[\"marco\", \"age\", \"2026-08-01\"]"⟩  -- vigencia
  , ⟨4, 1065352320, some 1065368160, "attribute[\"rex\", \"color\", \"2026-08-01\"]"⟩  -- vigencia
  , ⟨4, 1065368160, none, "attribute[\"rex\", \"color\", \"2026-08-12\"]"⟩  -- vigencia
  , ⟨5, 1065369600, none, "attribute[\"tomas\", \"excluded\", \"2026-08-13\"]"⟩  -- vigencia
  ]

/-- Vigencias de `excluded`: desde su inicio, la entidad no puede estar presente. -/
def exclusions : List Exclusion :=
  [ ⟨5, 1065369600, none, "attribute[\"tomas\", \"excluded\", \"2026-08-13\"]"⟩  -- excluida
  ]

def chronicle : Chronicle :=
  { presences, births, ages, existences, validities, exclusions }

/-- I1. Nadie esta presente en una escena anterior a su nacimiento, y la edad declarada cuadra con la fecha de nacimiento. -/
theorem i1_born_before_present : I1.check chronicle = true := by decide +kernel

/-- I2. Nadie esta en dos lugares en el mismo instante. -/
theorem i2_one_place_at_a_time : I2.check chronicle = true := by decide +kernel

/-- I3. Ninguna vigencia termina antes de empezar ni empieza antes de que exista su entidad. -/
theorem i3_validity_ordered : I3.check chronicle = true := by decide +kernel

/-- I4. Nadie esta presente en una escena posterior al instante desde el que esta excluido. -/
theorem i4_absent_after_exclusion : I4.check chronicle = true := by decide +kernel

end Chronology
