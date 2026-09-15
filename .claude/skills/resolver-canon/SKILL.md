---
name: resolver-canon
description: Entrega el canon ya resuelto a la fecha de una escena, en prosa. Usala antes de escribir, corregir o criticar cualquier escena.
---

Nadie interpreta YAML por su cuenta. El canon se pide resuelto:

    python harness/scripts/resolver_canon.py books/<slug> S014

o, equivalente:

    python harness/scripts/run_scene.py books/<slug> contexto S014

Es un **script y no un juicio** porque tiene una respuesta correcta: la edad sale
de `nacimiento`, el estado del tramo vigente, la etapa de la pareja del arco. Lo
que se puede calcular no se recuerda.

Lo que devuelve, ya en prosa:

- Quien esta, con su edad **a esa fecha** y su estado vigente.
- Que sabe cada uno a esa fecha, y **que todavia no sabe** (esto ultimo es lo que
  evita el error mas comun: reaccionar a algo que aun no ocurrio).
- En que etapa esta la relacion, y la orden de no moverla.
- Que no puede aparecer por epoca.
- La forma obligatoria de la escena y que hilos cierra.

Usalo tal cual. **No lo reinterpretes ni lo resumas**: si algo falta, falta en el
canon, y eso se arregla en `context/`, no en el prompt.
