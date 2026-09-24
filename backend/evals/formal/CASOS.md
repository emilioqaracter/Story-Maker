# Casos de la verificación formal

`specs/srs-backend-v4.md` RF-272. Un caso que `check.formal` (Lean 4 sobre la cronología del canon) detecta y los verificadores deterministas de texto no. VER-04, VER-10.

## Caso 1 · El excluido que vuelve sin fecha

**Mutación declarada como tal.** Ninguna tirada real de T52 dio `formal.lean` con `passed=false`: las cinco comprobaciones que registran las trazas de `eval-01` (capítulos 1 a 3), `eval-02` (capítulo 1) y `eval-01-umbral3` (capítulo 1) demostraron la cronología en 1,0 a 1,3 s. El caso se construye sobre la fixture limpia de `verification/formal/fixtures`, que se crea con la API del canon (brief, congelación y delta), no con filas escritas a mano.

| | |
|---|---|
| **Canon de partida** | La fixture limpia. Tomás está presente en `c1e1` y `c1e3`, y el delta del capítulo 1 fija `excluded = marcha` el 2026-08-13 |
| **Mutación** | Una escena por congelar, `c3e1`, el 2026-08-30, en el parque, con Tomás presente. Prosa: «Tomás volvió al parque aquella tarde y se sentó en el banco, junto a Lucía.» |
| **Invariante** | I4 · `i4_absent_after_exclusion`: nadie está presente en una escena posterior al instante desde el que está excluido |
| **`check.formal`** | **Falla.** Refuta `i4_absent_after_exclusion` antes de congelar, con dos filas de origen: `pending:chronology["c3e1", "tomas"]` y `attribute["tomas", "excluded", "2026-08-13"]`. En el motor sería un S1 que impide congelar el capítulo |
| **`check.timeline`** | **Pasa.** Solo lee fechas en formato explícito («30 de agosto», `2026-08-30`), y la prosa no nombra ninguna |
| **`check.availability`** | **Pasa.** Solo corre en la escena de encuentro y solo recibe lesionados y sancionados del canon. `excluded` no es ninguno de los dos, así que su lista llega vacía |
| **Continuista** | Fuera del caso: es un modelo, y lo que se compara aquí son comprobaciones deterministas (`AGENTS.md` §5.3.4) |

Por qué importa: la prosa es coherente frase a frase. La contradicción solo aparece al cruzar la presencia de la escena con la vigencia de un atributo del canon, y eso es exactamente lo que la cronología generada le da a Lean.

**Prueba reproducible**

```
cd backend
PATH="$HOME/.elan/bin:$PATH" python -m pytest evals/formal/test_case.py -q
```

`test_case.py` tiene tres pruebas:

- sin la mutación, Lean demuestra la cronología;
- con ella, falla exactamente I4 con las dos filas de origen;
- `check.timeline` y `check.availability` no marcan nada sobre la misma prosa.

Sin `lake`, las dos primeras se saltan. La puerta no depende de ellas para exigir Lean: su paso «verificacion formal (Lean)» falla sin `lake`.
