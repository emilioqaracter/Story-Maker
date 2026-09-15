---
name: formato-critica
description: El JSON exacto de la rubrica y el veto. Usala al emitir cualquier critica de escena.
---

Este formato **es el contrato de la puerta G2**: `gate_scene.py` parsea esta
salida. No es cosmetica, y un campo de mas o de menos no abre la puerta.

Se escribe en `books/<slug>/manuscript/chNN/SNNN.critique.json`. Las dos lentes
escriben el mismo archivo: continuidad llena `continuidad`, calidad llena
`calidad`.

```json
{
  "escena": "S014",
  "intento": 2,
  "continuidad": {
    "veto": true,
    "hallazgos": [
      {"que": "Marco conduce un coche que no aparece hasta S021",
       "cita": "arranco el Falcon y salio a la ruta"}
    ]
  },
  "calidad": {
    "conflicto":  {"nota": 2, "cita": null},
    "dialogo":    {"nota": 1, "cita": "Ya sabes que el club no paga desde marzo."},
    "concrecion": {"nota": 0, "cita": "Marco estaba angustiado."},
    "frescura":   {"nota": 2, "cita": null},
    "quimica":    {"nota": 1, "cita": "Sofia le alcanzo el bolso y se fue."}
  }
}
```

## Reglas del formato

- Las cinco dimensiones siempre estan. La unica que admite `null` entero es
  `quimica`, y solo si en la escena no estan los dos protagonistas.
- `nota` es 0, 1 o 2. Nada mas.
- **Toda nota menor que 2 lleva `cita`** con texto literal de la escena. Sin
  cita, `gate_scene.py` trata la dimension como no evaluada y la puerta no abre.
- `cita` puede ser `null` solo cuando la nota es 2.
- `veto: false` con `hallazgos: []` es el resultado normal. No fuerces hallazgos.
- No pongas una nota global, ni un veredicto, ni una recomendacion de aprobar.
  **Vos no decidis si la escena pasa.** Suma y umbral son del script.
