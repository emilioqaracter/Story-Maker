/-
Hechos de la cronología que exporta `verification/formal/generate.py`.

`specs/srs-backend-v4.md` RF-243, RD-41, D-87. Cada hecho es una fila del
canon, o de lo que está por congelar, y lleva su origen en `src`: tabla e
identificador. Las entidades y los lugares van como naturales; el generador
escribe al lado de cada uno a qué identificador del canon corresponde.

El tiempo es un natural: minutos desde el 1 de enero del año 1 a las 00:00
(D-87). Un natural hace que todas las comparaciones sean decidibles, y los
minutos cubren un instante con hora sin perder los días.
-/

namespace StoryMaker

/-- Un personaje presente en una escena de la cronología (`chronology`, RF-242).
`seq` es el desempate del instante del canon (MUN-05): dos escenas son del
mismo instante solo si coinciden en `time` y en `seq`. -/
structure Presence where
  entity : Nat
  time : Nat
  seq : Nat
  place : Option Nat
  src : String
  deriving Repr

/-- El nacimiento de una persona como intervalo `[lo, hi]` en minutos.
Declarado (`birth_date`): `lo = hi`. Derivado de `age`: el intervalo de un año
compatible con la edad, y `derived = true` (MET-09). Si no hay ninguno de los
dos atributos no hay hecho: el nacimiento está ausente y nunca se inventa. -/
structure Birth where
  entity : Nat
  lo : Nat
  hi : Nat
  derived : Bool
  src : String
  deriving Repr

/-- Una edad declarada (`age`): el intervalo `[lo, hi]` de nacimientos
compatibles con tener esos años cumplidos en el instante de su vigencia. -/
structure Age where
  entity : Nat
  lo : Nat
  hi : Nat
  src : String
  deriving Repr

/-- Desde cuándo existe una entidad (`entity.created_at`). -/
structure Existence where
  entity : Nat
  created : Nat
  src : String
  deriving Repr

/-- Una vigencia de atributo, alias, relación o competencia (MET-07).
`stop = none` es vigencia abierta. -/
structure Validity where
  entity : Nat
  start : Nat
  stop : Option Nat
  src : String
  deriving Repr

/-- Una vigencia del atributo reservado `excluded`: desde `start`, la entidad
no puede estar presente (muerte o marcha definitiva). -/
structure Exclusion where
  entity : Nat
  start : Nat
  stop : Option Nat
  src : String
  deriving Repr

/-- La cronología entera de una novela. -/
structure Chronicle where
  presences : List Presence
  births : List Birth
  ages : List Age
  existences : List Existence
  validities : List Validity
  exclusions : List Exclusion
  deriving Repr

end StoryMaker
