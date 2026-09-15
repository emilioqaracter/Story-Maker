# Spec 11: Personajes reales

**Decisión D14:** los personajes reales **pueden aparecer**. Único requisito de
admisión: **tener perfil en Wikipedia**.

## 1. Por qué el criterio funciona

"Tiene artículo en Wikipedia" no es una opinión: es una consulta HTTP con
respuesta binaria. Encaja con el principio rector del sistema — se verifica por
código, no lo juzga un LLM. Además aporta gratis los datos que el validador
necesita: fecha de nacimiento, fecha de muerte y trayectoria.

```
  El DRAFTER quiere usar a "X"
              │
              ▼
   ¿está en context/real-figures.yaml?
        │ no                    │ sí
        ▼                       ▼
  scripts/verify_figure.py   admitido
        │
        ├── ¿artículo en Wikipedia?  no ──► RECHAZADO (regla R01)
        │                             │      -> usar un personaje ficticio
        └── sí ──► extrae birth/death, trayectoria y URL canónica
                   ──► alta en real-figures.yaml (requiere OK humano)
```

La verificación guarda la **URL canónica**, nunca el nombre: evita homónimos
("hay tres futbolistas con ese nombre en Wikipedia" es un caso real, no teórico).

## 2. ⑧ `context/real-figures.yaml`

Octavo archivo del Context Store. Append-only como el ledger; lo escribe
`LEDGER_WRITER` tras la verificación.

```yaml
figures:
  - id: rf_ejemplo
    display_name: "Nombre Apellido"
    wikipedia:
      url: https://es.wikipedia.org/wiki/...      # canónica, resuelve homónimos
      lang: es
      verified_at: 2026-09-15
      revision_id: 123456789                      # el artículo cambia; esto fija qué se leyó
    birth_date: 1960-10-30
    death_date: null                              # null = vivo -> ver §3
    status: living                                # living | deceased
    known_for: [futbolista, seleccion_argentina]
    real_timeline:                                # extraído del artículo, alimenta R04
      - { from: 1984-01-01, to: 1991-06-30, club: "..." }
    max_interaction: backdrop                     # tope permitido (§3)
    notes: "Solo en partidos documentados en el corpus ⑦."
```

## 3. Niveles de interacción

El nivel no limita *quién* aparece — eso ya lo decide Wikipedia. Limita **cuánto
se inventa** sobre esa persona. Es la diferencia entre ficción histórica y
poner palabras en la boca de alguien.

| Nivel | Qué permite | Ejemplo |
|---|---|---|
| `mention` | se le nombra, no aparece en escena | "todos hablaban de su gol" |
| `backdrop` | aparece en un hecho **documentado en ⑦** | juega el partido que realmente jugó |
| `interaction` | habla con personajes ficticios; diálogo inventado | se cruzan en el vestuario |
| `intimate` | pensamientos, decisiones privadas, motivaciones inventadas | su duda antes de la final |

### Política por defecto

| Estado de la figura | Tope por defecto | Razón |
|---|---|---|
| `deceased` | `interaction` | convención habitual de la ficción histórica |
| `living` | `backdrop` | atribuir diálogo o intenciones inventadas a alguien vivo es donde aparecen los problemas de derechos de personalidad |

> Es un **valor por defecto configurable**, no un veto. Subir a `interaction` o
> `intimate` una figura viva se hace poniéndolo explícitamente en su
> `max_interaction`, y el validador lo respeta. La decisión es del autor; el
> sistema solo se asegura de que sea deliberada y quede registrada.

### Regla transversal

Ninguna figura real, viva o muerta, puede aparecer haciendo algo **deshonroso,
delictivo o difamatorio** que no esté documentado en el corpus ⑦. Esto no es una
cuestión de nivel de interacción: es la línea que separa la ficción histórica de
un problema legal, y aplica en todos los niveles. La lente L2 tiene veto aquí.

## 4. Reglas de validación — grupo R

Se añaden al catálogo de la spec 04.

| ID | Regla | Sev |
|---|---|---|
| R01 | Toda persona real nombrada en la prosa está dada de alta en ⑧ (y por tanto verificada en Wikipedia) | ERROR |
| R02 | La escena no supera el `max_interaction` de esa figura | ERROR |
| R03 | La figura no aparece antes de `birth_date` ni después de `death_date` | ERROR |
| R04 | Lo que hace es compatible con su `real_timeline` (no juega en un club donde no estaba) | ERROR |
| R05 | Todo hecho atribuido con `source: real` existe en el corpus ⑦ | ERROR |
| R06 | Conducta deshonrosa o delictiva no documentada en ⑦ | ERROR (veto L2) |
| R07 | Densidad: ninguna escena gira **sobre** una figura real; son marco, no protagonistas | WARN |

R07 es un aviso de deriva, no un error: si la novela empieza a tratar sobre
figuras reales en vez de sobre Marco, la premisa (D3: protagonista ficticio) se
está rompiendo poco a poco.

## 5. `scripts/verify_figure.py`

```
verify_figure.py --name "Nombre Apellido" --lang es
```

1. Consulta la API de Wikipedia (sin credenciales, sin coste, sin cuota de OpenRouter).
2. Si hay **cero** resultados → salida `REJECTED`, y el DRAFTER debe usar un personaje ficticio.
3. Si hay **varios** (homónimos) → salida `AMBIGUOUS` con la lista; decide el humano.
4. Si hay **uno** → extrae `birth_date`, `death_date`, `revision_id` y la trayectoria;
   propone el alta en ⑧, que confirma el humano.

Se ejecuta en `/story outline`, no durante la redacción: así el elenco real queda
fijado antes de escribir y no hay sorpresas a mitad de capítulo.

## 6. Nota del autor

La obra terminada incluye la nota estándar del género, generada automáticamente
a partir de ⑧:

> Esta es una obra de ficción. El protagonista y la trama son inventados.
> Algunas figuras públicas reales aparecen en un marco histórico documentado;
> sus diálogos y escenas son ficticios y no pretenden representar hechos reales.

Si `real-figures.yaml` está vacío, la nota se omite.

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial (decisión D14). Criterio de admisión por Wikipedia, archivo ⑧, niveles de interacción con política por defecto, reglas R01-R07 y script de verificación. |
