/-
Las cuatro invariantes de la cronología (`specs/srs-backend-v4.md` RF-244, D-87).

Cada una tiene tres piezas:

* `check`, una función booleana. Es lo que el fichero generado demuestra
  `by decide` sobre los hechos exportados.
* `Spec`, su especificación proposicional: lo que la invariante dice, sin
  pensar en cómo se calcula.
* `check_iff`, el lema que las relaciona. Sin él, un `decide` verde probaría
  que una función devuelve `true`, no que la historia cumple la invariante.

`violations` no forma parte de la prueba: devuelve el origen de los hechos que
rompen la invariante, y solo se evalúa para informar cuando `check` falla.
-/
import StoryMaker.Types

namespace StoryMaker

/-- ¿La exclusión `x` impide estar presente en el instante `t`? Desde su
inicio, sin incluirlo, y hasta su fin, sin incluirlo. -/
def Exclusion.covers (x : Exclusion) (t : Nat) : Prop :=
  x.start < t ∧ ∀ s, x.stop = some s → t < s

instance (x : Exclusion) (t : Nat) : Decidable (x.covers t) :=
  match h : x.stop with
  | none => if hs : x.start < t then isTrue ⟨hs, by simp [h]⟩
            else isFalse (fun hc => hs hc.1)
  | some s => if hs : x.start < t ∧ t < s then isTrue ⟨hs.1, by simp [h, hs.2]⟩
              else isFalse (fun hc => hs ⟨hc.1, hc.2 s h⟩)

/-- ¿La vigencia `v` termina después de empezar, o no termina? -/
def Validity.ordered (v : Validity) : Prop :=
  ∀ s, v.stop = some s → v.start ≤ s

instance (v : Validity) : Decidable v.ordered :=
  match h : v.stop with
  | none => isTrue (by intro s hs; simp [h] at hs)
  | some s => if hs : v.start ≤ s then isTrue (by intro s' h'; simp [h] at h'; omega)
              else isFalse (fun hc => hs (hc s h))

/-! ### I1 · Nadie aparece antes de nacer, y la edad cuadra con el nacimiento -/

namespace I1

def Spec (c : Chronicle) : Prop :=
  (∀ p ∈ c.presences, ∀ b ∈ c.births, b.entity = p.entity → b.lo ≤ p.time) ∧
  (∀ a ∈ c.ages, ∀ b ∈ c.births, b.entity = a.entity → a.lo ≤ b.hi ∧ b.lo ≤ a.hi)

def check (c : Chronicle) : Bool :=
  c.presences.all (fun p => c.births.all (fun b =>
    !decide (b.entity = p.entity) || decide (b.lo ≤ p.time))) &&
  c.ages.all (fun a => c.births.all (fun b =>
    !decide (b.entity = a.entity) || (decide (a.lo ≤ b.hi) && decide (b.lo ≤ a.hi))))

theorem check_iff (c : Chronicle) : check c = true ↔ Spec c := by
  simp only [check, Spec, Bool.and_eq_true, List.all_eq_true, Bool.or_eq_true,
    Bool.not_eq_true', decide_eq_false_iff_not, decide_eq_true_eq]
  constructor
  · rintro ⟨h1, h2⟩
    exact ⟨fun p hp b hb he => (h1 p hp b hb).resolve_left (fun hn => hn he),
           fun a ha b hb he => (h2 a ha b hb).resolve_left (fun hn => hn he)⟩
  · rintro ⟨h1, h2⟩
    exact ⟨fun p hp b hb => (Classical.em (b.entity = p.entity)).elim
             (fun he => Or.inr (h1 p hp b hb he)) Or.inl,
           fun a ha b hb => (Classical.em (b.entity = a.entity)).elim
             (fun he => Or.inr (h2 a ha b hb he)) Or.inl⟩

def violations (c : Chronicle) : List String :=
  (c.presences.flatMap fun p => (c.births.filter fun b =>
      decide (b.entity = p.entity) && !decide (b.lo ≤ p.time)).map fun b =>
        s!"{p.src}\t{b.src}") ++
  (c.ages.flatMap fun a => (c.births.filter fun b =>
      decide (b.entity = a.entity) && !(decide (a.lo ≤ b.hi) && decide (b.lo ≤ a.hi))).map
        fun b => s!"{a.src}\t{b.src}")

end I1

/-! ### I2 · Nadie está en dos lugares en el mismo instante -/

namespace I2

def Spec (c : Chronicle) : Prop :=
  ∀ p ∈ c.presences, ∀ q ∈ c.presences,
    p.entity = q.entity → p.time = q.time → p.seq = q.seq →
    p.place.isSome → q.place.isSome → p.place = q.place

/-- Dos presencias chocan si son de la misma entidad, en el mismo instante y en
dos lugares conocidos distintos. `Nat.beq` y no `decide`: el núcleo la calcula
directamente, y esta comparación se hace para cada par. -/
def clash (p q : Presence) : Bool :=
  Nat.beq p.entity q.entity && Nat.beq p.time q.time && Nat.beq p.seq q.seq &&
  match p.place, q.place with
  | some a, some b => !Nat.beq a b
  | _, _ => false

theorem clash_iff (p q : Presence) : clash p q = true ↔
    p.entity = q.entity ∧ p.time = q.time ∧ p.seq = q.seq ∧
    p.place.isSome ∧ q.place.isSome ∧ p.place ≠ q.place := by
  unfold clash
  cases hp : p.place <;> cases hq : q.place <;> simp [Nat.beq_eq, and_assoc, ← Bool.not_eq_true]

theorem clash_symm (p q : Presence) : clash p q = clash q p := by
  apply Bool.eq_iff_iff.mpr
  simp only [clash_iff]
  constructor <;> rintro ⟨h1, h2, h3, h4, h5, h6⟩ <;>
    exact ⟨h1.symm, h2.symm, h3.symm, h5, h4, Ne.symm h6⟩

theorem clash_self (p : Presence) : clash p p = false := by
  apply Bool.eq_false_iff.mpr
  intro h
  exact ((clash_iff p p).mp h).2.2.2.2.2 rfl

/-- Cada par se mira una sola vez: `clash` es simétrica y nadie choca consigo
mismo, así que basta con la mitad de los pares. -/
def pairwise : List Presence → Bool
  | [] => true
  | p :: rest => rest.all (fun q => !clash p q) && pairwise rest

theorem pairwise_iff (l : List Presence) :
    pairwise l = true ↔ ∀ p ∈ l, ∀ q ∈ l, clash p q = false := by
  induction l with
  | nil => simp [pairwise]
  | cons p rest ih =>
    simp only [pairwise, Bool.and_eq_true, List.all_eq_true, Bool.not_eq_true', ih,
      List.mem_cons]
    constructor
    · rintro ⟨hp, hr⟩ x hx y hy
      rcases hx with hx | hx <;> rcases hy with hy | hy
      · subst hx; subst hy; exact clash_self _
      · subst hx; exact hp y hy
      · subst hy; rw [clash_symm]; exact hp x hx
      · exact hr x hx y hy
    · intro h
      exact ⟨fun q hq => h p (Or.inl rfl) q (Or.inr hq),
             fun x hx y hy => h x (Or.inr hx) y (Or.inr hy)⟩

def check (c : Chronicle) : Bool := pairwise c.presences

theorem check_iff (c : Chronicle) : check c = true ↔ Spec c := by
  simp only [check, Spec, pairwise_iff]
  constructor
  · intro h p hp q hq he ht hs hps hqs
    exact Classical.byContradiction fun hne =>
      absurd ((clash_iff p q).mpr ⟨he, ht, hs, hps, hqs, hne⟩) (by simp [h p hp q hq])
  · intro h p hp q hq
    apply Bool.eq_false_iff.mpr
    intro hc
    obtain ⟨he, ht, hs, hps, hqs, hne⟩ := (clash_iff p q).mp hc
    exact hne (h p hp q hq he ht hs hps hqs)

def violations (c : Chronicle) : List String := go c.presences
where
  go : List Presence → List String
  | [] => []
  | p :: rest => (rest.filter (clash p)).map (fun q => s!"{p.src}\t{q.src}") ++ go rest

end I2

/-! ### I3 · Ninguna vigencia termina antes de empezar ni empieza antes de su entidad -/

namespace I3

def Spec (c : Chronicle) : Prop :=
  (∀ v ∈ c.validities, v.ordered) ∧
  (∀ v ∈ c.validities, ∀ e ∈ c.existences, e.entity = v.entity → e.created ≤ v.start)

def check (c : Chronicle) : Bool :=
  c.validities.all (fun v => decide v.ordered) &&
  c.validities.all (fun v => c.existences.all (fun e =>
    !decide (e.entity = v.entity) || decide (e.created ≤ v.start)))

theorem check_iff (c : Chronicle) : check c = true ↔ Spec c := by
  simp only [check, Spec, Bool.and_eq_true, List.all_eq_true, Bool.or_eq_true,
    Bool.not_eq_true', decide_eq_false_iff_not, decide_eq_true_eq]
  constructor
  · rintro ⟨h1, h2⟩
    exact ⟨h1, fun v hv e he hq => (h2 v hv e he).resolve_left (fun hn => hn hq)⟩
  · rintro ⟨h1, h2⟩
    exact ⟨h1, fun v hv e he => (Classical.em (e.entity = v.entity)).elim
             (fun hq => Or.inr (h2 v hv e he hq)) Or.inl⟩

def violations (c : Chronicle) : List String :=
  (c.validities.filter fun v => !decide v.ordered).map (fun v => v.src) ++
  (c.validities.flatMap fun v => (c.existences.filter fun e =>
      decide (e.entity = v.entity) && !decide (e.created ≤ v.start)).map fun e =>
        s!"{v.src}\t{e.src}")

end I3

/-! ### I4 · Nadie está presente después de quedar excluido -/

namespace I4

def Spec (c : Chronicle) : Prop :=
  ∀ p ∈ c.presences, ∀ x ∈ c.exclusions, x.entity = p.entity → ¬ x.covers p.time

def check (c : Chronicle) : Bool :=
  c.presences.all (fun p => c.exclusions.all (fun x =>
    !decide (x.entity = p.entity) || !decide (x.covers p.time)))

theorem check_iff (c : Chronicle) : check c = true ↔ Spec c := by
  simp only [check, Spec, List.all_eq_true, Bool.or_eq_true, Bool.not_eq_true',
    decide_eq_false_iff_not]
  constructor
  · intro h p hp x hx he
    exact (h p hp x hx).resolve_left (fun hn => hn he)
  · intro h p hp x hx
    exact (Classical.em (x.entity = p.entity)).elim (fun he => Or.inr (h p hp x hx he)) Or.inl

def violations (c : Chronicle) : List String :=
  c.presences.flatMap fun p => (c.exclusions.filter fun x =>
    decide (x.entity = p.entity) && decide (x.covers p.time)).map fun x =>
      s!"{p.src}\t{x.src}"

end I4

end StoryMaker
