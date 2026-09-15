# Spec 05: El panel crítico

**Decisión D4:** veto duro en canon; consultivo con umbral en calidad literaria.

## 1. Por qué un panel y no un crítico

Un crítico único promedia todo y devuelve "está bastante bien" siempre.
Cuatro lentes independientes, en paralelo, con criterios disjuntos:

```
                      escena en borrador
                              │
       ┌────────────┬─────────┴────────┬─────────────┐
       ▼            ▼                  ▼             ▼
  CONTINUITY   PLAUSIBILIDAD       LITERARIO      LECTOR
   (canon vs     DEPORTIVA        (voz, ritmo,   (¿me aburrí?
    escena)    (táctica, cuerpo,   diálogo,       ¿qué me
                calendario)        clichés)       chirrió?)
       │            │                  │             │
    VETO         VETO               score 1-10    señal
       └────────────┴─────────┬────────┴─────────────┘
                              ▼
                      VERDICT MERGER
        bloquea si: cualquier VETO  o  score_literario < umbral (def. 6)
                              │
                              ▼
                   feedback accionable -> REVISER
```

## 2. Las lentes

### L1 — CONTINUITY  *(veto duro)*
Recibe la escena + el canon resuelto a esa fecha. Busca lo que el validador
no puede formalizar: contradicciones implícitas, cambios de carácter sin causa,
objetos que aparecen sin haber sido introducidos, conocimiento inferido.

### L2 — PLAUSIBILIDAD DEPORTIVA  *(veto duro)*
¿Un entrenador haría eso? ¿Ese calendario es posible? ¿Esa recuperación es
realista? ¿La jerga es la correcta del país y la época?

**Responsabilidad adicional (D14):** cuando la escena incluye una figura real,
L2 juzga si lo que se le atribuye es coherente con su carácter público
documentado, y **veta** cualquier conducta deshonrosa o delictiva que no esté
en el corpus ⑦ (regla R06). El validador comprueba fechas y niveles; esto
requiere criterio y por eso vive aquí.

### L3 — LITERARIO  *(consultivo con umbral)*
Rúbrica numérica versionada (§3). Sin rúbrica, un crítico LLM genera opiniones
aleatorias entre ejecuciones.

### L4 — LECTOR  *(señal, no bloquea)*
Simula lectura ingenua: dónde se perdió el interés, qué no se entendió, qué
frase sacó de la historia. Es la lente que más mejora el resultado y la que
menos debe bloquear.

## 3. Rúbrica literaria (v1)

| Criterio | Peso | 1-3 | 4-6 | 7-8 | 9-10 |
|---|:--:|---|---|---|---|
| Objetivo dramático | 20% | no pasa nada | pasa algo sin tensión | conflicto claro | conflicto con giro |
| Voz y POV | 20% | genérico | inconsistente | consistente | inconfundible |
| Diálogo | 15% | expositivo | funcional | con subtexto | revela carácter |
| Concreción sensorial | 15% | abstracto | tópicos | detalle específico | detalle revelador |
| Ritmo | 15% | plano | irregular | controlado | deliberado |
| Ausencia de clichés | 15% | plagado | algunos | limpio | fresco |

`score_literario` = media ponderada. Umbral por defecto: **6.0** (configurable).

## 4. Reglas anti-degeneración

| Regla | Motivo |
|---|---|
| El crítico **no reescribe**, solo diagnostica | su propia prosa nunca sería criticada |
| El crítico **no sabe el número de intento** | evita la aprobación complaciente en el intento 3 |
| Feedback obligatoriamente anclado a un span del texto | "mejora el ritmo" es inútil; "cortar párrafos 3-5" es accionable |
| Máximo 5 findings por lente, ordenados por impacto | un crítico que lista 30 cosas paraliza al REVISER |
| Las lentes no se ven entre sí | evita el efecto manada |

## 5. Formato de salida

```json
{
  "scene_id": "S014",
  "verdict": "blocked",
  "blocking_reason": "L1_CONTINUITY",
  "lenses": {
    "L1": {"veto": true, "findings": [
      {"span": [880, 940],
       "issue": "Sofia menciona el fichaje. En S007 solo se entera Marco; ella lo sabe desde S021.",
       "canon_ref": "canon-ledger F014",
       "fix": "Que Sofia pregunte en vez de afirmar, o adelantar la revelacion."}]},
    "L2": {"veto": false, "findings": []},
    "L3": {"score": 7.1, "breakdown": {"objetivo": 8, "voz": 7, "dialogo": 6}},
    "L4": {"attention_drop_at": [1200, 1600], "note": "tres parrafos de contexto historico frenan la escena"}
  }
}
```

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial. Panel de 4 lentes, rúbrica literaria ponderada, reglas anti-degeneración y formato de veredicto. |
| 0.2 | 2026-09-15 | emilioqaracter | La lente L2 asume el veto sobre conducta atribuida a figuras reales (regla R06, decisión D14). |
