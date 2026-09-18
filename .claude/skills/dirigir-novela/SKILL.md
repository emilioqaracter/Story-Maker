---
name: dirigir-novela
description: Dirige la escritura de una novela de punta a punta - crea el libro, despacha a los agentes, lee sus luces y aprueba los capitulos. Usala cuando pidan escribir una novela, seguir una empezada o saber como va.
---

# Dirigir una novela

Vos sos el orquestador. No hay ningun script que conduzca esto: **lo conducis
vos**, con las herramientas normales de la terminal y despachando subagentes.

Lo unico que no podes hacer nunca es **decidir que un capitulo esta bien**. Eso
lo deciden el revisor y el verificador, y vos acatas.

Tu trabajo es mecanico y esta escrito aqui paso a paso. No hace falta pensar
mucho entre despachos: mirar la carpeta, despachar, leer una linea, seguir.

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
  continuidad/
    01.md                      los hechos que fijo el capitulo 1, ya aprobado
    02.borrador.md             los del 2, a la espera de que el capitulo entre
  novela.md                    al final
```

**El estado es la carpeta.** No hay contadores en ningun lado. Para saber donde
estas, mira los archivos:

```bash
ls books/<slug>/capitulos books/<slug>/decisiones books/<slug>/continuidad
```

- Un capitulo **aprobado** es el que no lleva `borrador` en el nombre.
- El **intento en curso** es el numero mas alto que aparece en `decisiones/`.
- Lo que **falta** sale de comparar eso con la lista de capitulos de `plan.md`.

Leelo vos. No hay script que lo interprete, y no hace falta.

## Como se despacha un agente

Cada despacho es una llamada a la herramienta Agent con dos campos que
importan:

- `subagent_type`: el agente, tal cual: `arquitecto`, `redactor`, `revisor`,
  `verificador`, `director`.
- `description`: **empieza siempre por el nombre del agente**, y sigue con el
  capitulo y el intento. Exactamente asi:

| Despacho | `description` |
|---|---|
| el arquitecto | `arquitecto · plan` |
| el redactor escribiendo el 3 | `redactor · cap 03 · intento 1` |
| el redactor corrigiendo el 3 | `redactor · cap 03 · intento 2` |
| el revisor | `revisor · cap 03 · intento 2` |
| el verificador | `verificador · cap 03 · intento 2` |
| el director | `director · estado` |

Ese campo es **lo que Langfuse muestra como nombre del subagente** en el grafo
de la traza. Si lo escribis de otra manera, en Langfuse el agente se llama
"Subagent: lo que hayas puesto" y no se puede seguir quien hizo que.

## Empezar una novela

1. Elegi un slug corto: protagonista y ano, por ejemplo `sara-1994`.
2. `mkdir -p books/<slug>/capitulos books/<slug>/decisiones books/<slug>/continuidad`
3. Despacha al **arquitecto** con la idea del usuario, la longitud pedida y la
   ruta. Escribe `plan.md`.
4. Lee el plan. Si algo te chirria, decilo antes de escribir una sola linea:
   un plan flojo se paga siete veces.

Si el usuario no dijo longitud, elegi vos una novela corta de unas 6000
palabras y avisa de lo que elegiste.

## El ciclo de un capitulo

```
                                 ┌──► REVISOR ─────┐
  REDACTOR ──► borrador ─────────┤                 ├──► dos verdes: el capitulo entra
      ▲                          └──► VERIFICADOR ─┘
      │                                   │
      └──── alguna roja: la ruta de la luz ┘
```

Por cada capitulo del plan, en orden:

### 1. Redactor

Le decis la ruta de la novela, el numero de capitulo y el intento. Si es una
correccion, le das ademas **las rutas de los archivos de luz roja** de ese
intento, una por linea. No las abras vos ni las copies en el prompt: el
redactor tiene Read y las lee enteras. Asi la luz le llega tal como la escribio
el juez, y a vos no se te llena el contexto con textos que no tenes que juzgar.

```
Novela: books/<slug>. Capitulo 03, intento 2.
Es una correccion. Lee enteras estas luces rojas y atendelas:
- books/<slug>/decisiones/03.intento1.verificador.md
```

Escribe `capitulos/<NN>.borrador.md`.

### 2. Los dos jueces, a la vez

Antes de despacharlos, un solo `Bash` que saca lo que el revisor necesita del
plan y de la terminal:

```bash
p=books/<slug>/plan.md; b=books/<slug>/capitulos/<NN>.borrador.md
echo "--- voz ---";      sed -n '/^## La voz/,/^## /{/^## /d;p}' "$p"
echo "--- pedidas ---";  grep -E "^### Cap[ií]tulo <N> -" "$p" | grep -oE "[0-9]+ palabras"
echo "--- tiene ---";    wc -w < "$b"
```

(`<N>` va sin cero delante: `Capitulo 3`, no `Capitulo 03`.)

Despues, **en el mismo mensaje, dos llamadas a Agent**:

- **Revisor.** Ruta del borrador, capitulo, intento, y las tres cosas de arriba
  copiadas en el prompt: la voz, las palabras pedidas y las que tiene. No le
  digas donde esta `plan.md` ni que pasa en el capitulo: no es su pregunta.
  Escribe `decisiones/<NN>.intento<K>.revisor.md`.
- **Verificador.** Ruta de la novela, capitulo, intento. Escribe
  `decisiones/<NN>.intento<K>.verificador.md` y, si da verde,
  `continuidad/<NN>.borrador.md`.

Van a la vez porque hacen dos preguntas distintas y ninguno debe saber lo que
dijo el otro. Cuestan lo mismo, y despacharlos en serie solo alarga el reloj.

### 3. Leer las luces

```bash
head -1 books/<slug>/decisiones/<NN>.intento<K>.revisor.md
head -1 books/<slug>/decisiones/<NN>.intento<K>.verificador.md
```

La primera linea dice `LUZ: VERDE` o `LUZ: ROJA`. Debajo esta el motivo, que
vos **no necesitas leer**: si es roja, quien lo lee es el redactor.

Si una primera linea no es ninguna de las dos, esa decision no se entiende:
repeti **esa** llamada, solo esa. **No la interpretes vos.** Que un juez se
haya explicado mal no te convierte en el juez.

En el mismo `Bash`, manda cada luz a Langfuse como score (ver mas abajo).

### 4. Decidir el paso

- **Alguna roja:** volve al paso 1 con las rutas de las luces rojas de este
  intento (una o las dos). Es el intento K+1.
- **Las dos verdes: el capitulo entra.**
  ```bash
  mv books/<slug>/capitulos/<NN>.borrador.md    books/<slug>/capitulos/<NN>.md
  mv books/<slug>/continuidad/<NN>.borrador.md  books/<slug>/continuidad/<NN>.md
  ```
  Esos dos cambios de nombre **son** la aprobacion. Un capitulo corregido
  vuelve a entrar por el principio: las dos luces se piden de nuevo.

### Tres intentos y paras

Si un capitulo llega al tercer intento sin las dos verdes, **para**. No lo
mandes a un cuarto. Contale al usuario que se atasco, pegale los motivos que
se repiten y preguntale si prefiere cambiar el plan o bajar el liston.

### Cuando no sepas como seguir

Despacha al **director**. Le das la ruta de la novela y te dice el proximo paso
y por que. Usalo cuando retomes una novela a medias, cuando te pierdas, o
cuando el usuario pregunte como va.

Para el camino normal no hace falta: el ciclo de arriba se sigue solo.

## Las luces en Langfuse

Cada luz se manda tambien a Langfuse como **score de la sesion**, para poder
comparar corridas sin abrir carpetas: cuantas rojas hubo, que juez rechaza mas,
si un cambio en un agente bajo los reintentos.

Se hace en el mismo `Bash` del paso 3, justo despues del `head -1`, con el
valor que acabas de leer:

```bash
npx -y langfuse-cli --env .env api scores create --body-json '{
  "name": "luz-revisor",
  "value": "VERDE",
  "dataType": "CATEGORICAL",
  "sessionId": "'"$CLAUDE_CODE_SESSION_ID"'",
  "comment": "<slug> cap <NN> intento <K>",
  "metadata": {"novela": "<slug>", "capitulo": "<NN>", "intento": <K>, "juez": "revisor"}
}' >/dev/null 2>&1 || true
```

Igual para el verificador, con `"name": "luz-verificador"` y `"juez":
"verificador"`. `sessionId` es la sesion de Claude Code, que es la misma que
el plugin de Langfuse usa para agrupar las trazas, asi que el score cae en la
misma sesion que los despachos.

**Esto nunca para el ciclo.** Por eso lleva `|| true`: si no hay red, si falta
`.env` o si Langfuse no responde, la luz sigue estando en `decisiones/` y el
ciclo sigue. La traza en disco es la que manda; Langfuse es una copia comoda.

## Cerrar la novela

Cuando todos los capitulos del plan esten aprobados:

```bash
{ head -1 books/<slug>/plan.md; echo; cat books/<slug>/capitulos/[0-9][0-9].md; } > books/<slug>/novela.md
```

La primera linea del plan es el titulo de la novela, y asi el libro empieza
por su titulo y no por "Capitulo 1". El patron con dos digitos deja fuera los
borradores a proposito: un capitulo que no paso las dos luces no es parte de
la novela.

## Mientras trabajas

Deci una linea por capitulo aprobado y una por luz roja, **con el motivo real**
del que juzgo, no con un resumen tuyo que lo suavice. Para eso si podes leer el
titulo del primer bloque de la luz roja (`grep -m1 '^## '`), que es el motivo
en una frase. El usuario tiene que poder seguir lo que pasa sin abrir un
archivo.

## Lo que nunca haces

- **No decidis que un capitulo esta bien.** Ni siquiera cuando es obvio, ni
  cuando el juez te parece injusto, ni para desatascar.
- **No escribis ni retocas prosa.** Si algo hay que cambiar, vuelve al
  redactor.
- **No cambias el plan.** Si el plan esta mal, se lo decis al usuario y lo
  cambia el arquitecto.
- **No despachas a un juez solo** salvo para repetir una luz que no se
  entendio. Los dos van a la vez y ninguno sabe lo que dijo el otro.
- **No resumis ni copias una luz roja** al pasarsela al redactor. Le das la
  ruta y la lee entera.
- **No le das el plan al revisor.** Solo la voz y los numeros de palabras, en
  el prompt.
- **No paras el ciclo porque Langfuse no responda.**
