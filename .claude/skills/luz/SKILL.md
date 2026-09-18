---
name: luz
description: El formato exacto de una decision sobre un capitulo - luz verde o luz roja, con su motivo. Usala al emitir cualquier juicio sobre un capitulo de la novela.
---

# El formato de una luz

Una luz es tu veredicto sobre un capitulo. La escribis en un archivo Markdown.

**La primera linea del archivo es siempre una de estas dos, exacta, sin nada
mas en esa linea:**

```
LUZ: VERDE
```

```
LUZ: ROJA
```

Quien orquesta lee esa linea y nada mas. Si no esta, o esta mal escrita, tu
decision no se interpreta: se repite la llamada. Escribila exacta.

## Luz verde

Despues de la primera linea, una linea en blanco y dos o tres frases diciendo
por que pasa. No hace falta que sea largo, pero tiene que existir: es lo que
permite leer despues una corrida entera y entender que criterio se aplico.

```markdown
LUZ: VERDE

El capitulo cumple lo que el plan pedia y la voz se sostiene. La escena del
taller carga el peso con objetos y no con adjetivos. Lo mas flojo es el
dialogo del final, que explica de mas, pero no llega a justificar un rechazo.
```

Una luz verde tambien puede senalar lo mas flojo. No obliga a nada, pero ayuda
al que lee la traza despues.

## Luz roja

Despues de la primera linea, un bloque por cada problema. **Cada bloque lleva
las tres cosas**, siempre:

```markdown
LUZ: ROJA

## El protagonista sabe algo que todavia no paso

**Donde:** «Marta ya sabia que el equipo la dejaria fuera de la Vuelta.»

**Que cambiar:** la decision del equipo se comunica en el capitulo 7. Aqui
Marta puede sospecharlo o temerlo, pero no darlo por hecho.

## El capitulo se queda corto

**Donde:** el capitulo tiene 430 palabras y el plan pide 900.

**Que cambiar:** falta desarrollar la conversacion con el entrenador, que en el
plan es lo que hace girar el capitulo y aqui se resuelve en dos lineas.

**Leccion:** Te quedas corto cuando el plan pide una conversacion: dale a cada
escena del plan el espacio que pide antes de cerrar el capitulo.
```

| | |
|---|---|
| **El titulo del bloque** | que esta mal, en una frase |
| **Donde** | una cita textual del capitulo, para no discutir de memoria |
| **Que cambiar** | que tendria que pasar para que la luz fuera verde |
| **Leccion** | al final de la luz, una frase que pueda acabar copiada en las instrucciones del redactor como regla permanente: el habito que falla, dicho como se escribe bien. En una roja va siempre; en una verde, solo si hay algo flojo que se repite |

## Las reglas

- **Sin cita no hay rechazo.** Si no podes senalar el sitio exacto, no es un
  problema del capitulo, es una impresion tuya.
- **"Que cambiar" es una instruccion, no una queja.** El que lo lee es el
  redactor y tiene que poder actuar.
- **No reescribas el capitulo.** Ni siquiera un parrafo de ejemplo. Tu trabajo
  es decir que esta mal, no arreglarlo.
- **Se proporcionado.** Una coma discutible no es una luz roja. Rechaza lo que
  de verdad impide que el capitulo entre en el libro.
- **Como mucho cuatro problemas.** Si hay mas, elegi los cuatro que mas pesan.
  Una lista de quince cosas no se puede corregir de una vez.
- **La leccion no lleva citas ni nombres.** Es la unica parte de la luz que
  habla del habito y no del capitulo: si solo sirve para esta historia, no es
  una leccion. Lo que fallo aqui ya esta en los bloques.
- **La leccion no se gasta en erratas.** Las tildes, las palabras cortadas, la
  concordancia y los terminos que cambian de grafia los limpia el redactor solo
  antes de entregar el borrador. Si eso es lo unico que te chirrio, la luz
  puede ser roja, pero sin leccion.
- **Las citas van literales.** Copia el texto del capitulo tal cual, con sus
  tildes y sus comillas. Si la cita no coincide con el original, el redactor no
  encuentra lo que le senalas.
