---
name: formato-critica
description: El JSON exacto que devuelven las dos lentes - el veredicto, el veto de continuidad y la rubrica con cita. Usala al emitir cualquier critica de escena.
---

# El formato de una critica

Dos lentes, dos llamadas separadas, un solo archivo. El script las junta.

## La lente de continuidad

```json
{"continuidad": {"veto": false, "hallazgos": [{"que": "...", "cita": "..."}]}}
```

Un hallazgo cierra la puerta **aunque pongas `veto: false`**: encontrar una
contradiccion con el canon y no vetarla no es una salida coherente. Sin cita no
es un hallazgo, es una impresion.

## La lente de calidad

```json
{"veredicto": {"pasa": true, "motivo": "..."},
 "calidad": {"conflicto": {"nota": 2, "cita": "..."},
             "voz": {"nota": 1, "cita": "..."},
             "concrecion": {"nota": 2, "cita": "..."},
             "frescura": {"nota": 2, "cita": "..."},
             "avance": {"nota": 2, "cita": "..."}}}
```

**El veredicto es quien decide** desde la v9.0. El `motivo` es obligatorio y no
es para el expediente: es lo unico que recibe el corrector. Un motivo vago
gasta un intento entero.

**La rubrica ya no decide**: es la medida que permite comparar corridas. Toda
nota exige cita textual, el 2 incluido — un script lo comprueba.

## El archivo que se guarda

Las dos respuestas juntas, en `manuscript/chNN/SNNN.critique.json`:

```json
{"escena": "S001",
 "veredicto": {"pasa": false, "motivo": "el protagonista no decide nada"},
 "continuidad": {"veto": false, "hallazgos": []},
 "calidad": { ... }}
```

Tiene que escribirse **despues** de la prosa que critica: una critica mas vieja
que su escena habla de un texto que ya no existe, y G2 la rechaza por eso.
