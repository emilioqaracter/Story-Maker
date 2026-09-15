---
name: corregir-escena
description: Reescribe solo lo que senalan los errores del validador o el veto del critico. Usala cuando G1 o G2 no abren.
---

Corregis **solo lo senalado**. Sin esto, cada arreglo reescribe de mas y la voz
se mueve: a los tres intentos la escena ya no se parece a la que aprobo el
capitulo anterior.

## Procedimiento

1. Lee `SNNN.validation.json` y `SNNN.critique.json`. Cada error trae regla,
   mensaje y **arreglo**. El arreglo no es una sugerencia: es lo que hay que
   hacer.
2. Toca unicamente las lineas implicadas. Si un error cita un fragmento,
   reescribi ese fragmento, no el parrafo entero.
3. Respeta la forma: si cambias una linea, sigue teniendo entre 9 y 15 palabras,
   y el parrafo sigue teniendo 4 lineas. Un arreglo que rompe V15 no es un
   arreglo.
4. No aproveches para mejorar otra cosa. Lo que paso las puertas se queda.

## Lo que no se toca nunca

- El canon. Si la escena contradice `context/`, se cambia la escena. Un ciclo que
  edita el canon para que su texto pase deja de validar nada.
- La etapa de la relacion a esa fecha.
- Los hilos que la escena cierra.

Devolve la escena completa, con la correccion aplicada. Solo la prosa.
