---
name: entrevistar
description: El cuestionario fijo de doce preguntas que llena el canon de un libro nuevo. Usala al arrancar una novela, antes de investigar o planificar nada.
---

# El cuestionario

Doce preguntas, en este orden, una por vez. **No improvises preguntas nuevas**:
si cada libro se pregunta distinto, cada canon sale con una forma distinta.

Solo se pregunta lo que **solo el usuario puede decidir**. Lo verificable es del
`researcher`; lo derivable es del `planner`. Ninguna de estas doce es de esos
tipos, y por eso son doce y no cuarenta.

| # | Pregunta | Llena | Tipo |
|---|---|---|---|
| 1 | Que deporte? | `deporte` | uno, y con calendario encontrable |
| 2 | En que ano o rango de fechas? | `epoca` | `{desde, hasta}` ISO |
| 3 | Donde? | `lugar` | ciudad o pais real |
| 4 | A que nivel se compite? | `nivel` | amateur / profesional / seleccion |
| 5 | Quien es la primera persona? Nombre y fecha de nacimiento | `persona_a` | nombre + fecha ISO |
| 6 | Que hace en ese mundo? | `persona_a.rol` | texto corto |
| 7 | Quien es la segunda persona? Nombre y fecha de nacimiento | `persona_b` | nombre + fecha ISO |
| 8 | Esta dentro del deporte o fuera? | `persona_b.rol` | texto corto |
| 9 | Como se cruzan por primera vez? | `encuentro` | una frase |
| 10 | **Que los separa?** | `obstaculo` | una frase |
| 11 | Que tiene que perder cada uno para estar con el otro? | `precio` | `{a, b}` |
| 12 | Ademas de la relacion, que dos cosas estan en juego? | `hilos` | exactamente 2 |

Las que cargan el peso del genero son la **10** y la **11**. Sin obstaculo no hay
romance, hay dos personas simpaticas. Y la 11 es la que hace que la pregunta
dramatica se pueda responder, porque si acaban juntos ya lo sabemos.

**El tamano no se pregunta.** Sale del perfil de `harness/config.yaml`.

# Como preguntar

- Una por vez. En la 1, 2 y 4, ofrece opciones en vez de campo libre.
- Valida la respuesta al recibirla, contra el tipo de la tabla. Una fecha que no
  es fecha se vuelve a preguntar en el momento.
- En las preguntas 1 a 4, no saber es valido: va a `pendiente_investigar`. De la
  5 a la 12 no lo es.
- No propongas contenido. Pedir que aclare, si; sugerir, no.

# La salida

Un solo archivo, `books/<slug>/context/intake.json`:

```json
{
  "version": 1,
  "fecha": "AAAA-MM-DD",
  "respuestas": {
    "deporte": "futbol",
    "epoca": {"desde": "1990-01-01", "hasta": "1990-12-31"},
    "lugar": "Rosario, Argentina",
    "nivel": "profesional",
    "persona_a": {"nombre": "", "nacimiento": "AAAA-MM-DD", "rol": ""},
    "persona_b": {"nombre": "", "nacimiento": "AAAA-MM-DD", "rol": ""},
    "encuentro": "",
    "obstaculo": "",
    "precio": {"a": "", "b": ""},
    "hilos": ["", ""]
  },
  "pendiente_investigar": []
}
```

Es inmutable: es lo que dijo el usuario. Si manana cambia como se derivan los
YAML del canon, se regeneran desde aqui sin repetir la entrevista.
