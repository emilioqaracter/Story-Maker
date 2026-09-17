---
name: preparar-libro
description: Convierte una idea suelta en un canon que abre G0 - deriva lo derivable, investiga lo investigable y pregunta solo lo que cambia el libro. Usala antes de escribir una sola escena, cuando no hay libro todavia.
---

# Preparar un libro

De "una novela de ciclismo en los 80" a un canon que abre G0.

Antes habia una entrevista de doce preguntas fijas, siempre las mismas y
siempre en el mismo orden. Se fue por dos razones: preguntaba cosas que el
propio harness puede calcular, y preguntaba lo mismo para un libro de boxeo en
1950 que para uno de natacion en 2024.

## El criterio: tres cubos

Todo dato del canon cae en uno de estos tres, y **de donde sale cambia segun
cual sea**. Antes de preguntar nada, clasifica.

| Cubo | Ejemplos | De donde sale |
|---|---|---|
| **Se calcula** | en que acto cae cada escena, las fechas, cuantas escenas hay, el techo de palabras | `harness/derivaciones.py`. Nunca se pregunta y nunca se guarda: se deriva. |
| **Se averigua** | que no existia en esa epoca y como se vivia entonces | el agente `researcher`. No se pregunta: se busca. |
| **Se decide** | quien es, que quiere, que se lo impide, que le cuesta | una persona, o vos si te dieron via libre |

Preguntar algo del primer cubo es pedirle al usuario que haga de calculadora.
Preguntar algo del segundo es pedirle que haga de enciclopedia. **Solo se
pregunta el tercero, y solo la parte que no se deduce de lo que ya te dijeron.**

## El recorrido

### 1. Exprimi la idea

Sacale a la frase que te dieron todo lo que ya trae: deporte, epoca, lugar,
nivel, tono. Una idea de dos lineas suele traer la mitad del cubo tres.

### 2. Rellena el resto con criterio

La novela es de **un solo protagonista**. Puede ser cualquier cosa que le pase
a alguien que compite: volver de una lesion, llegar a una final, retirarse,
cambiar de deporte, entrenar a quien lo reemplazo. No hay pareja, no hay
etapas de relacion: hay una persona, algo que quiere, y lo que le cuesta.

Cuatro cosas que si salen flojas el libro no se sostiene:

- **La meta.** Concreta y comprobable: "volver a jugar un partido oficial
  antes de que se le acabe el contrato", no "recuperar la ilusion". Si no se
  puede saber si la consiguio, el desenlace no puede existir.
- **El obstaculo.** Por que no puede, hoy. Lo mejor es que sea estructural —un
  cuerpo roto, un contrato, una federacion, una familia— y no una duda que se
  resuelve decidiendo.
- **El precio.** Que pierde por intentarlo. Si no pierde nada, no hay historia:
  hay un entrenamiento largo.
- **Los dos hilos.** Lo que esta en juego ademas de la meta. Cada uno lo cierra
  una escena concreta, asi que tienen que ser cosas que se puedan **resolver**,
  no temas.

Y una que se deriva sola: **los tres actos**. No los inventes, se calculan
sobre la ventana de la epoca (25/50/25). Lo unico que tenes que cuidar es que
la historia tenga sitio para los tres — con menos de tres escenas no lo tiene,
y el harness deja de exigirlo porque seria una regla incumplible.

### 3. Pregunta UNA vez, y solo lo que mueve el libro

Con lo anterior hecho, mira que te queda dudoso. Si algo tiene una respuesta
razonable y el libro funciona igual con cualquiera de las dos, **no preguntes:
elegi y decilo**.

Para lo que si cambia el libro, una sola tanda con `AskUserQuestion`: hasta
cuatro preguntas, con opciones concretas (no "¿que te parece?"), y cada opcion
diciendo que consecuencia tiene. Ese es el limite — si te salen ocho, es que
seis eran del cubo uno o del dos.

Las que suelen valer la pena:

- **La forma**: cuantas escenas. Tres es el minimo que cuenta una historia (una
  por acto); menos sirve para probar el circuito, no para contar algo. Cambia
  el techo de palabras y cuanto tarda.
- **Como acaba**: si consigue la meta o no. Las dos son finales validos, y
  cambian el libro entero.
- **El tono**: si el deporte es el escenario o es el tema.
- **Quien mas hay**: si la idea no trae a nadie, uno o dos secundarios con un
  papel claro bastan. No hagan falta mas.

Si te dijeron "hacelo vos" o "no me preguntes", **no preguntes**: decidi todo y
deci en dos lineas que decidiste, para que puedan corregirte antes de que
escribas.

### 4. Crea el libro

Arma el JSON con el formato de la cabecera de `crear_libro.py` y corre:

    python harness/scripts/crear_libro.py <ruta.json>

El canon lo escribe el script, nunca vos. Te devuelve el resultado de G0 de
regalo.

### 5. Investiga la epoca

Task al `researcher`. Lo que se le pide es **coherencia, no exhaustividad**:
que en 1800 no haya telefonos y en 2010 si haya internet. No le pidas
calendarios ni fechas de competiciones: eso salio del canon a proposito.

Nunca te inventes la lista vos: si no sabes si algo existia, no entra. Guardas
lo que devuelva con:

    python harness/scripts/guardar_plan.py <libro> epoca < datos.json

### 6. G0

`python harness/scripts/validate_canon.py <libro>`. Si abre, el libro existe y
podes pasarle el relevo a `dirigir-novela`.

Si cierra, mira que regla:

- **V13** (`epoca.yaml` sin anacronismos): el paso 5 fallo. Volve a investigar —
  sin esa lista, la epoca es decorativa y no hay nada que vetar.
- **V16** (el arco): falta meta, obstaculo o precio, o el protagonista no tiene
  ficha. Es del cubo tres: decidilo y volve a crear.
- **el plan no cabe bajo el techo**: la `estructura` es lo unico del canon que
  todavia se puede cambiar sin romper la regla — ajustala y volve a crear.
- **cualquier otra**: el canon esta mal derivado. Paralo y decilo; no lo
  parchees a mano.

## Lo que no se hace

- **No edites `context/` a mano.** Ni para arreglar G0. Lo escribe un script.
- **No inventes fuentes** para que V13 calle.
- **No preguntes en cadena.** Doce preguntas seguidas cansan y la numero nueve
  se contesta de cualquier manera. Una tanda, y a trabajar.
