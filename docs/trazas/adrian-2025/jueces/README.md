# Llamadas al modelo de los jueces · `adrian-2025`

Exportado de la traza [72176debd982d1e2fdc855eed2dc452f](https://cloud.langfuse.com/project/cmu5tos9r011oad0de26hskjq/traces/72176debd982d1e2fdc855eed2dc452f) de Langfuse (sesión `3de17a9d-2a94-4c4d-9d03-e199831b866f`, 2026-09-18). Un archivo por despacho de juez, con el encargo, cada llamada al modelo en orden, su texto visible, sus herramientas (qué leyó, qué escribió, qué devolvió) y su coste. `llamadas.jsonl` tiene lo mismo en crudo, una línea por llamada.

Lo que **no** está en ningún sitio: el razonamiento interno del modelo. Cuenta en los tokens de salida, pero ni el plugin de Langfuse ni la transcripción local de Claude Code lo guardan.

| Juez | Cap | Intento | Luz | Llamadas | Tokens totales | Tokens salida | USD | Segundos | Archivo |
|---|---|---|---|---|---|---|---|---|---|
| revisor | 01 | 1 | ROJA | 4 | 51249 | 3576 | 0.079 | 37 | [revisor-cap01-intento1.md](revisor-cap01-intento1.md) |
| verificador | 01 | 1 | ROJA | 6 | 130396 | 11829 | 0.194 | 102 | [verificador-cap01-intento1.md](verificador-cap01-intento1.md) |
| revisor | 01 | 2 | VERDE | 4 | 45839 | 2009 | 0.047 | 20 | [revisor-cap01-intento2.md](revisor-cap01-intento2.md) |
| verificador | 01 | 2 | VERDE | 4 | 77489 | 9573 | 0.150 | 96 | [verificador-cap01-intento2.md](verificador-cap01-intento2.md) |
| revisor | 02 | 1 | VERDE | 4 | 46689 | 2200 | 0.050 | 24 | [revisor-cap02-intento1.md](revisor-cap02-intento1.md) |
| verificador | 02 | 1 | ROJA | 5 | 105221 | 11853 | 0.188 | 115 | [verificador-cap02-intento1.md](verificador-cap02-intento1.md) |
| revisor | 02 | 2 | VERDE | 4 | 48489 | 2770 | 0.057 | 29 | [revisor-cap02-intento2.md](revisor-cap02-intento2.md) |
| verificador | 02 | 2 | VERDE | 5 | 112392 | 14037 | 0.216 | 128 | [verificador-cap02-intento2.md](verificador-cap02-intento2.md) |
| revisor | 03 | 1 | ROJA | 4 | 46081 | 1911 | 0.046 | 19 | [revisor-cap03-intento1.md](revisor-cap03-intento1.md) |
| verificador | 03 | 1 | VERDE | 6 | 134326 | 10212 | 0.181 | 85 | [verificador-cap03-intento1.md](verificador-cap03-intento1.md) |
| revisor | 03 | 2 | VERDE | 4 | 43985 | 1218 | 0.038 | 13 | [revisor-cap03-intento2.md](revisor-cap03-intento2.md) |
| verificador | 03 | 2 | VERDE | 4 | 94524 | 11454 | 0.184 | 100 | [verificador-cap03-intento2.md](verificador-cap03-intento2.md) |
| revisor | 04 | 1 | ROJA | 4 | 44885 | 1835 | 0.044 | 19 | [revisor-cap04-intento1.md](revisor-cap04-intento1.md) |
| verificador | 04 | 1 | ROJA | 6 | 121433 | 6488 | 0.134 | 61 | [verificador-cap04-intento1.md](verificador-cap04-intento1.md) |
| revisor | 04 | 2 | VERDE | 4 | 43520 | 1344 | 0.038 | 15 | [revisor-cap04-intento2.md](revisor-cap04-intento2.md) |
| verificador | 04 | 2 | VERDE | 5 | 102171 | 8664 | 0.154 | 71 | [verificador-cap04-intento2.md](verificador-cap04-intento2.md) |
| revisor | 05 | 1 | ROJA | 4 | 55054 | 4984 | 0.085 | 49 | [revisor-cap05-intento1.md](revisor-cap05-intento1.md) |
| verificador | 05 | 1 | ROJA | 5 | 119781 | 13745 | 0.220 | 138 | [verificador-cap05-intento1.md](verificador-cap05-intento1.md) |
| revisor | 05 | 2 | ROJA | 4 | 49359 | 2873 | 0.059 | 29 | [revisor-cap05-intento2.md](revisor-cap05-intento2.md) |
| verificador | 05 | 2 | ROJA | 5 | 120081 | 13644 | 0.219 | 118 | [verificador-cap05-intento2.md](verificador-cap05-intento2.md) |
| revisor | 05 | 3 | VERDE | 4 | 52075 | 3922 | 0.072 | 42 | [revisor-cap05-intento3.md](revisor-cap05-intento3.md) |
| verificador | 05 | 3 | VERDE | 5 | 127996 | 16511 | 0.255 | 150 | [verificador-cap05-intento3.md](verificador-cap05-intento3.md) |

| Juez | Despachos | Llamadas | Tokens salida | USD |
|---|---|---|---|---|
| revisor | 11 | 44 | 28642 | 0.62 |
| verificador | 11 | 56 | 128010 | 2.10 |
