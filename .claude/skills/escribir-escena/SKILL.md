---
name: escribir-escena
description: Redacta una escena a partir de sus beats y del canon ya resuelto. Usala al escribir cualquier escena del manuscrito.
---

Una sola voz para el libro entero. No hay variantes por tipo de escena: una
escena de accion y una intima se diferencian en **que pasa**, no en quien las
narra.

La novela es de un protagonista: **el punto de vista es suyo y no se mueve**.
Lo que sienten los demas se ve desde fuera, en lo que hacen.

Antes de escribir, leé dos cosas: el canon resuelto (`resolver-canon`) y
`context/voz.md`, la muestra de como suena este libro.

## La voz

- Tercera persona, pasado. Un solo punto de vista por escena.
- La emocion no se nombra: se ve en lo que el cuerpo hace mientras habla.
- El deporte es oficio, no espectaculo: desde dentro, con su ruido y su
  cansancio, nunca como lo narraria una transmision.
- El dialogo no informa al lector de nada que los que hablan ya sepan.
- Lo que no se dice pesa mas que lo que se dice. Las frases cortas cierran.
- Nada de metaforas de manual: ni corazones que laten fuerte, ni miradas que se
  cruzan, ni tiempos que se detienen.

## La forma

La marca `config.yaml` y la comprueban V14 y V15. En el perfil v1:

- **3 parrafos exactos**, separados por una linea en blanco.
- **4 lineas por parrafo**, exactas. Un salto de linea real por linea.
- **12 palabras por linea**, mas o menos 3. Ni 8 ni 16.

No es un capricho de formato: es lo que hace verificable el documento.

## Que devolver

Solo la prosa. Sin titulo, sin encabezado, sin notas, sin resumen, sin comillas
alrededor. Se escribe en `books/<slug>/manuscript/chNN/SNNN.md` y nada mas.
