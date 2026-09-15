# Spec 06: Registro de decisiones

## Cerradas

| ID | Decisión | Valor | Fecha |
|---|---|---|---|
| D1 | Stack | Claude Code: subagentes + skill + scripts (spec 09) | 2026-09-15 |
| D1b | Motor de prosa | OpenRouter, modelos `:free`, vía script (spec 10) | 2026-09-15 |
| D2 | Granularidad | Escena + gate humano por capítulo | 2026-09-15 |
| D3 | Realismo | Híbrido: protagonista ficticio, mundo real | 2026-09-15 |
| D4 | Autoridad del crítico | Veto duro en canon, consultivo en estilo (umbral 6.0) | 2026-09-15 |
| D5 | Alcance deportivo | Fútbol primero, `sport` como plugin (spec 08) | 2026-09-15 |
| D6 | Research | Corpus curado, revisado por humano y congelado (⑦) | 2026-09-15 |
| D7 | Retcon | Permitido con revalidación en cascada (spec 07) | 2026-09-15 |
| D8 | Formato | Español, ~40k palabras, 10-12 capítulos, ~45 escenas | 2026-09-15 |
| D14 | Personajes reales | Permitidos; único requisito: perfil en Wikipedia (spec 11) | 2026-09-15 |

## Ronda 3 — abiertas

| ID | Pregunta | Impacto |
|---|---|---|
| D9  | ¿POV único (Marco) o múltiple? | Multi-POV multiplica la complejidad de `knowledge` y de la regla C05 |
| D10 | Criterio de "obra terminada" | ¿Nº de capítulos fijo, o cierre de todos los hilos de ⑥? |
| D11 | Persistencia | Ficheros planos + git (recomendado) vs base de datos |
| D12 | Evals del crítico | ¿Se versiona la rúbrica y se comparan ejecuciones entre versiones? |
| D13 | Edición manual del usuario | Si el usuario reescribe prosa a mano, hay que re-ingerir sus cambios al ledger |
| D21 | Tope por defecto de figuras vivas | La spec 11 propone `backdrop` para vivos e `interaction` para fallecidos. ¿Se acepta o se sube? |
| D15 | Exportación | Markdown / EPUB / DOCX |
| D16 | Suite de tests | Escenas-trampa con errores plantados (cumpleaños duplicado, edad errónea, jugar lesionado) para verificar que el validador los caza |
| D17 | Presupuesto económico | Coste máximo por novela; determina `max_tokens_per_chapter` |
| D18 | **Cuota de OpenRouter** | ~145 llamadas necesarias vs ~50/día en free. ¿Cargar $10 (→~1000/día) o ejecutar por lotes en varios días? Bloquea la planificación temporal |
| D19 | Modelos concretos de la cadena | Elegir los `:free` vigentes al arrancar y ordenarlos por calidad de prosa en español |
| D20 | ¿El extractor de aserciones se fusiona con el draft? | Ahorra ~45 llamadas, pero degrada ambas salidas en modelos pequeños |

## Siguiente paso propuesto

1. **D16** — fixture con 10 escenas-trampa y sus findings esperados. Valida que
   las specs 01 y 04 son correctas sin gastar una sola llamada a modelo.
2. **`scripts/validate.py`** — se prueba contra ese fixture. Cero dependencia de LLM.
3. **`scripts/or_draft.py`** — adaptador con la cadena de fallback, probado con
   una escena de juguete para medir la cuota real disponible.
4. Recién entonces, los subagentes y el ciclo completo.

Este orden deja lo dependiente de red y de cuota para el final, cuando el resto
ya está verificado.

---

## Historial de revisiones

| Versión | Fecha | Autor | Cambios |
|:--:|---|---|---|
| 0.1 | 2026-09-15 | emilioqaracter | Versión inicial. Decisiones D1-D4 cerradas; rondas 2 y 3 abiertas. |
| 0.2 | 2026-09-15 | emilioqaracter | Cierre de D5-D8. La ronda 3 (D9-D17) queda como pendiente y se propone el fixture de escenas-trampa como siguiente paso. |
| 0.3 | 2026-09-15 | emilioqaracter | D1 revisada y D1b añadida. Nuevas preguntas D18-D20 derivadas de los límites del tier gratuito de OpenRouter. Plan de implementación en 4 pasos. |
| 0.4 | 2026-09-15 | emilioqaracter | Cierre de D14 (personajes reales admitidos con criterio Wikipedia). Nueva D21 sobre el tope por defecto de las figuras vivas. |
