# Spec 10: Motor de prosa — OpenRouter (tier gratuito)

**Decisión D1b:** la prosa la escriben modelos `:free` de OpenRouter.
Claude Code orquesta y critica; no redacta la novela.

## 1. El límite que condiciona el diseño

> Verifica los números vigentes en la cuenta antes de planificar: OpenRouter los ajusta.

| Restricción típica del tier free | Valor aproximado |
|---|---|
| Peticiones por minuto | ~20 |
| **Peticiones por día (sin créditos)** | **~50** |
| Peticiones por día (con ~$10 comprados una vez) | ~1000 |

### Presupuesto real de la novela (D8: ~45 escenas)

```
  45 escenas
×  1 draft                        =  45 llamadas
+  ~1.2 revisiones/escena media   =  54 llamadas
+  extractor de aserciones (C01/C05) = 45 llamadas
                                    ─────────────
                                     ~145 llamadas
```

**~145 llamadas frente a un techo de ~50/día.** Consecuencias de diseño, no opcionales:

| Mecanismo | Spec |
|---|---|
| **Cola persistente reanudable** — el estado vive en disco; si se agota la cuota, el ciclo para y retoma mañana donde iba | `run_scene.py` + `status` por escena |
| **Backoff y respeto de 429** — nunca reintentar en bucle contra el rate limit | adaptador |
| **El validador determinista corre primero** — filtra sin gastar cuota | spec 04 |
| **El extractor de aserciones se fusiona con el draft** cuando el modelo lo permite | ahorra 45 llamadas |
| **Contador de cuota local** — el ciclo sabe cuántas llamadas le quedan hoy y para limpio | `scripts/quota.json` |

> Recomendación directa: si el proyecto va en serio, cargar $10 una vez en OpenRouter
> multiplica la cuota por 20 y convierte "tres semanas" en "una tarde". Es la
> decisión de mejor relación coste/beneficio de todo el sistema.

## 2. Adaptador de modelos

Los modelos `:free` **rotan, se saturan y desaparecen** sin aviso. El adaptador
nunca cablea un nombre de modelo: lee una cadena de fallback declarativa.

`config/models.yaml`:
```yaml
roles:
  drafter:
    chain:                     # se prueba en orden ante 429 / 404 / error
      - modelo-a:free
      - modelo-b:free
      - modelo-c:free
    params: { temperature: 0.85, max_tokens: 2000 }

  reviser:
    chain: [modelo-a:free, modelo-b:free]
    params: { temperature: 0.4 }      # revisión = precisión, no invención
    escalate_to: claude               # intento 3 -> subagente de Claude Code

  extractor:                          # prosa -> aserciones estructuradas
    chain: [modelo-pequeño:free]
    params: { temperature: 0.0 }      # determinismo máximo
```

`or_draft.py --role drafter --scene S014` resuelve la cadena, llama, reintenta
y devuelve JSON por stdout. Ningún nombre de modelo aparece en el resto del código.

## 3. Prompting para modelos débiles

Un modelo `:free` no sigue instrucciones como Claude. El diseño lo compensa:

| Regla | Motivo |
|---|---|
| **Una tarea por llamada** | pedir prosa + JSON en la misma respuesta rompe una de las dos |
| **El contexto llega ya resuelto, en prosa** | "Marco, 28 años, lesionado hasta el 5 de abril" — nunca YAML crudo que deba interpretar |
| **Prompt corto y rígido** | los prompts largos y matizados degradan más rápido en modelos pequeños |
| **Instrucciones en positivo** | "escribe 800-1000 palabras" funciona mejor que "no te extiendas" |
| **Parseo tolerante** | los `:free` envuelven JSON en ```` ```json ````, añaden preámbulos; extraer el primer bloque válido y reintentar una vez con un recordatorio |
| **Sin `response_format` garantizado** | muchos modelos free no lo soportan de verdad; no dependas de él |

### Esqueleto del prompt del DRAFTER

```
Eres un novelista. Escribe UNA escena en español rioplatense, 800-1000 palabras.

CONTEXTO INMUTABLE
  Año: 1990. Marco Iriarte, 28 años, delantero de Newells.
  Estado hoy (2 de marzo de 1990): recuperándose de una rotura fibrilar,
  no puede jugar hasta el 5 de abril. Moral hundida.
  Sofía todavía NO sabe lo del fichaje.

LO QUE DEBE PASAR
  {beat sheet del PLANNER}

ESCENA ANTERIOR (últimas 200 palabras)
  {...}

REGLAS
  - Narrador en tercera persona, pasado.
  - No menciones tecnología posterior a 1990.
  - Termina la escena; no escribas la siguiente.
  - Responde SOLO con la prosa. Sin títulos, sin comentarios.
```

> El bloque "ESTADO HOY" es el corazón del sistema: el modelo nunca calcula
> edades ni interpreta rangos de fechas. Si lo hiciera, se equivocaría.

## 4. Política de escalada

```
 intento 1 ──► drafter free        ─┐
 intento 2 ──► reviser free         │  si el validador o el veto siguen fallando
 intento 3 ──► REVISER = Claude    ─┘  (subagente `reviser-escalated`)
 intento 4 ──► escalado al humano
```

El modelo débil hace el volumen; Claude entra solo donde el volumen falla.
Esto mantiene el coste cerca de cero sin dejar escenas rotas en la novela.

## 5. Privacidad y credenciales

- Los modelos `:free` de OpenRouter suelen operar bajo una política de datos que
  permite el uso de los prompts para entrenamiento. Para ficción original esto es
  una decisión del autor, no un problema técnico: **decídelo conscientemente** en
  los ajustes de privacidad de la cuenta antes de generar.
- `OPENROUTER_API_KEY` vive en el entorno. Nunca en el repo, nunca en un YAML de
  configuración, nunca en un prompt.
- `config/models.yaml` sí se versiona: no contiene secretos.

## 6. Registro

Cada llamada deja una línea en `logs/calls.jsonl`: escena, rol, modelo efectivo,
intento, tokens, latencia, código de error. Sin esto es imposible saber por qué
el capítulo 7 salió peor que el 6, ni qué modelo de la cadena está degradando.

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial (decisión D1b). Presupuesto de llamadas frente al límite del tier gratuito, adaptador con cadena de fallback, prompting para modelos débiles y política de escalada. |
