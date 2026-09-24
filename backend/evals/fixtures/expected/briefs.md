# Tabla por brief

Generada por `python -m evals.brief_table table` desde los extractos de las trazas (RF-269). No se edita a mano: se regenera.

«falló (n)» cuenta cada vez que el verificador marco, en todos los intentos; «no aplica», que la tirada no le dio nada que verificar.

| Brief | `outline.check` | `check.format` | `check.timeline` | `check.forbidden` | `check.repetition` | `check.lexicon` | `check.knowledge` | `check.ledger` | `check.availability` | `check.formal` | `continuity` | `quiz` | `jury.voice` | `jury.style_guide` | `jury.pacing` | `jury.subtext` | `jury.theme` | `work.close` | `check.novedad` |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01-semilla | pasó | pasó | pasó | pasó | pasó | pasó | pasó | pasó | pasó | no aplica | pasó | pasó | pasó | pasó | pasó | pasó | pasó | pasó | pasó |
| 03-temporal | falló (1) | pasó | falló (1) | pasó | falló (1) | pasó | pasó | no aplica | no aplica | falló (1) | falló (1) | falló (1) | falló (1) | pasó | pasó | pasó | pasó | falló (1) | pasó |
| 04-menor | pasó | pasó | pasó | falló (2) | pasó | pasó | pasó | no aplica | no aplica | no aplica | pasó | pasó | pasó | pasó | pasó | pasó | pasó | pasó | pasó |
| 05-no-deportivo | pasó | pasó | pasó | pasó | pasó | pasó | pasó | no aplica | no aplica | no aplica | pasó | no aplica | pasó | pasó | falló (1) | pasó | pasó | falló (1) | falló (1) |

## Tiradas

| Brief | Commit | Fecha | Cierre | `prompt_version` por agente |
|---|---|---|---|---|
| 01-semilla | `1a2b3c4` | 2026-09-20 | cerró | `arquitecto=a1b2c3d4e5f6`, `escritor=0f1e2d3c4b5a`, `jurado=99aa88bb77cc` |
| 03-temporal | `1a2b3c4` | 2026-09-21 | no cerró: deuda narrativa: el recuerdo del abuelo sin cobrar | `arquitecto=a1b2c3d4e5f6`, `escritor=0f1e2d3c4b5a`, `jurado=99aa88bb77cc` |
| 04-menor | `5e6f7a8` | 2026-09-22 | cerró | `arquitecto=a1b2c3d4e5f6`, `escritor=0f1e2d3c4b5a`, `jurado=99aa88bb77cc/dd11ee22ff33` |
| 05-no-deportivo | `5e6f7a8` | 2026-09-23 | sin work.close | sin llamadas a modelo |
