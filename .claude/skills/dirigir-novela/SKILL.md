---
name: dirigir-novela
description: Dirige la escritura de una novela de punta a punta - crea el libro, despacha a los agentes, lee sus luces y aprueba los capitulos. Usala cuando pidan escribir una novela, seguir una empezada o saber como va.
---

# Dirigir una novela

Vos sos el orquestador. No hay ningun script que conduzca esto: **lo conducis
vos**, con las herramientas normales de la terminal y despachando subagentes.

Lo unico que no podes hacer nunca es **decidir que un capitulo esta bien**. Eso
lo deciden el revisor y el verificador, y vos acatas.

## La carpeta de una novela

```
books/<slug>/
  plan.md                      el plan. Lo escribe el arquitecto
  capitulos/
    01.md                      aprobado: entra en la novela
    02.borrador.md             en curso, todavia sin aprobar
  decisiones/
    02.intento1.revisor.md     una luz, con su motivo
    02.intento1.verificador.md
  novela.md                    al final
```

**El estado es la carpeta.** No hay contadores en ningun lado. Para saber donde
estas, mira los archivos:

```bash
ls books/<slug>/capitulos books/<slug>/decisiones
```

- Un capitulo **aprobado** es el que no lleva `borrador` en el nombre.
- El **intento en curso** es el numero mas alto que aparece en `decisiones/`.
- Lo que **falta** sale de comparar eso con la lista de capitulos de `plan.md`.

Leelo vos. No hay script que lo interprete, y no hace falta.

## Empezar una novela

1. Elegi un slug corto: protagonista y ano, por ejemplo `sara-1994`.
2. `mkdir -p books/<slug>/capitulos books/<slug>/decisiones`
3. Despacha al **arquitecto** con la idea del usuario y la longitud pedida.
   Escribe `plan.md`.
4. Lee el plan. Si algo te chirria, decilo antes de escribir una sola linea:
   un plan flojo se paga siete veces.

Si el usuario no dijo longitud, elegi vos una novela corta de unas 6000
palabras y avisa de lo que elegiste.

## El ciclo de un capitulo

```
  REDACTOR ──► borrador ──► REVISOR ──► VERIFICADOR ──► el capitulo entra
      ▲                        │             │
      └──── luz roja ──────────┴─────────────┘
            y el motivo
```

Por cada capitulo del plan, en orden:

1. **Redactor.** Le decis la ruta, el numero de capitulo y, si es una
   correccion, las luces rojas que recibio. Escribe
   `capitulos/<NN>.borrador.md`.
2. **Revisor.** Escribe `decisiones/<NN>.intento<K>.revisor.md`.
3. **Si el revisor dio roja, volve al paso 1.** No llames al verificador: es la
   llamada mas cara y no tiene sentido comprobar si encaja algo que esta mal
   escrito.
4. **Verificador.** Escribe `decisiones/<NN>.intento<K>.verificador.md`.
5. **Si el verificador dio roja, volve al paso 1** con su motivo.
6. **Con las dos verdes, el capitulo entra:**
   ```bash
   mv books/<slug>/capitulos/<NN>.borrador.md books/<slug>/capitulos/<NN>.md
   ```
   Ese cambio de nombre **es** la aprobacion.

### Como se lee una luz

La primera linea del archivo dice `LUZ: VERDE` o `LUZ: ROJA`. Debajo esta el
motivo.

```bash
head -1 books/<slug>/decisiones/<NN>.intento<K>.revisor.md
```

Si la primera linea no es ninguna de las dos, la decision no se entiende:
repeti esa llamada. **No la interpretes vos.** Que un juez se haya explicado
mal no te convierte en el juez.

### Tres intentos y paras

Si un capitulo llega al tercer intento sin las dos verdes, **para**. No lo
mandes a un cuarto. Contale al usuario que se atasco, pegale los motivos que
se repiten y preguntale si prefiere cambiar el plan o bajar el liston.

### Cuando no sepas como seguir

Despacha al **director**. Le das la ruta de la novela y te dice el proximo paso
y por que. Usalo cuando retomes una novela a medias, cuando te pierdas, o
cuando el usuario pregunte como va.

Para el camino normal no hace falta: el ciclo de arriba se sigue solo.

## Cerrar la novela

Cuando todos los capitulos del plan esten aprobados:

```bash
cat books/<slug>/capitulos/[0-9][0-9].md > books/<slug>/novela.md
```

El patron con dos digitos deja fuera los borradores a proposito: un capitulo
que no paso las dos luces no es parte de la novela.

## Mientras trabajas

Deci una linea por capitulo aprobado y una por luz roja, **con el motivo real**
del que juzgo, no con un resumen tuyo que lo suavice. El usuario tiene que
poder seguir lo que pasa sin abrir un archivo.

## Lo que nunca haces

- **No decidis que un capitulo esta bien.** Ni siquiera cuando es obvio, ni
  cuando el juez te parece injusto, ni para desatascar.
- **No escribis ni retocas prosa.** Si algo hay que cambiar, vuelve al
  redactor.
- **No cambias el plan.** Si el plan esta mal, se lo decis al usuario y lo
  cambia el arquitecto.
- **No saltas al verificador** sin la luz verde del revisor.
- **No resumis una luz roja** al pasarsela al redactor. Se la pasas entera.
