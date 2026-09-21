# Story-Maker — El tablero · Especificación técnica

**Versión 1.4** · 2026-09-20 · el qué y el porqué están en
[SPEC-UI-FUNCIONAL.md](SPEC-UI-FUNCIONAL.md). El sistema que escribe la novela
está en [SPEC-TECNICO.md](SPEC-TECNICO.md).

Este documento dice **cómo está hecho**: carpetas, librerías, contratos y
formatos.

---

## 1. Estructura

```
ui/
  web/                      el front. Vite + React + TypeScript
    src/
      vistas/               el-circulo, el-expediente, la-cuenta, escribir-novela
      piezas/               nodos del grafo, la rejilla de luces, la tarjeta de luz,
                            el papel del manuscrito
      reloj/                el motor del replay, y el estado de una corrida en vivo
      lector/               de archivos a modelo, en el cliente (modo estatico)
      diseno/               tokens de color, tipografia y movimiento
        marca/              el logo de Qaracter, como lo entrego la empresa
  servidor/                 Node. Lee books/, vigila y lanza
    src/
      lector/               de archivos a modelo
      vigia/                chokidar sobre books/
      lanzador/             invoca a Claude Code
```

`books/` y `.claude/` **no se tocan**. El tablero no escribe un solo byte
dentro de ninguna de las dos, en ningún modo. Lo único que el servidor puede
provocar es que Claude Code escriba, igual que lo provoca la terminal.

---

## 2. Las librerías, y por qué cada una

| Pieza | Librería | Por qué esta |
|---|---|---|
| base | **Vite + React 19 + TypeScript** | arranque inmediato y recarga en caliente, que es la mitad del trabajo cuando se está afinando una animación |
| el grafo de agentes | **React Flow** (`@xyflow/react`) | nodos y aristas con posición, estados y aristas animadas, sin escribir un motor de grafos. Es la pieza que hace que la vista del círculo no parezca un diagrama estático |
| movimiento | **Motion** (`motion/react`) | transiciones de entrada y salida con `layout` automático: la rejilla de luces crece sola sin recolocar nada a mano |
| gráficas | **Recharts** | barras y series, que es todo lo que pide la vista de la cuenta. visx da más control y cuesta tres veces más código para este alcance |
| estilos | **Tailwind CSS v4** | los tokens de diseño viven en CSS y no en un objeto de JavaScript, así que la paleta se cambia en un archivo |
| componentes | **shadcn/ui** | el código entra en el repositorio y se puede tocar; no es una dependencia que imponga su estética |
| estado | **Zustand** | el reloj del replay es un store con suscripción y nada más. Redux sobra y el contexto de React no llega |
| servidor | **Fastify** + **chokidar** | Fastify trae SSE sin capas; chokidar es lo que funciona en Windows sin sorpresas |

**Las tipografías son parte de la arquitectura, no del adorno.** El híbrido de
la spec funcional se sostiene sobre dos familias y se rompe si se usa una:

- **Serif editorial** (Literata o Source Serif 4) para todo lo que escribió un
  agente: la prosa del capítulo, el motivo de una luz, la cita.
- **Monoespaciada** (JetBrains Mono) para todo lo que midió la máquina: costes,
  tokens, contadores, nombres de archivo, el reloj.

Nunca al revés. El lector aprende la regla en diez segundos sin que nadie se la
diga, y a partir de ahí sabe qué está mirando por la forma de la letra.

---

## 3. El modelo

Todo sale de la carpeta. El modelo no añade ni un campo que no esté en un
archivo.

```ts
type Novela = {
  slug: string
  titulo: string                  // primera linea de plan.md
  voz: string                     // seccion "## La voz" del plan
  capitulosPrevistos: CapPlan[]   // encabezados "### Capitulo N - ..."
  capitulos: Capitulo[]
  cierre: string | null           // novela.md, si existe
  cuenta: Cuenta | null           // sesion.json, si existe y no esta vacio
  estado: 'en curso' | 'terminada' | 'parada'
}

type Capitulo = {
  numero: number
  estado: 'pendiente' | 'en curso' | 'aprobado' | 'parado'
  texto: string | null            // NN.md, o NN.borrador.md si aun no entro
  esBorrador: boolean
  palabras: number
  intentos: Intento[]
  continuidad: Continuidad | null
}

type Intento = {
  k: number
  revisor: Luz | null
  verificador: Luz | null
}

type Luz = {
  juez: 'revisor' | 'verificador'
  veredicto: 'VERDE' | 'ROJA' | 'NO ENTENDIDA'
  bloques: { titulo: string; donde: string; queCambiar: string }[]
  refuerzo: string | null
  leccion: string | null
  crudo: string                   // el archivo entero, siempre
  ruta: string
}
```

**`crudo` no es opcional y no se descarta nunca.** Es lo que se enseña cuando el
veredicto es `NO ENTENDIDA`, y es lo que permite comprobar que el tablero no se
inventó nada. Un panel de la vista del expediente lo muestra a demanda.

### De qué archivo sale cada cosa

| Del sistema | Cómo se lee |
|---|---|
| el título | primera línea de `plan.md` |
| la voz | `## La voz` hasta el siguiente `## ` |
| los capítulos previstos | `### Capitulo N - <título> - <N> palabras - <parte>` |
| capítulo aprobado | `capitulos/NN.md` (dos dígitos, sin `borrador`) |
| capítulo en curso | `capitulos/NN.borrador.md` |
| intentos de un capítulo | los archivos `decisiones/NN.intentoK.*.md` |
| veredicto | primera línea: `LUZ: VERDE` o `LUZ: ROJA` |
| los hechos fijados | `continuidad/NN.md` |
| coste y tokens | `sesion.json` |

**El nombre del archivo es el contrato.** `NN.intentoK.juez.md` da capítulo,
intento y juez sin abrirlo, y eso es lo que permite ordenar una corrida entera
sin leer una sola línea de prosa. Es una propiedad del sistema, no una
casualidad, y el lector del tablero depende de ella igual que depende de ella
la sesión que orquesta.

### Las reglas del parser

1. **La primera línea manda.** Si no es exactamente `LUZ: VERDE` ni
   `LUZ: ROJA`, el veredicto es `NO ENTENDIDA` y se acabó. No se busca la
   palabra "verde" más abajo, no se adivina por el tono.
2. **Los marcadores son literales**, tal como los escribe la skill `luz`:
   `## ` abre un bloque de problema, y los cuatro marcadores van **sin tilde**
   —`**Donde:**`, `**Que cambiar:**`, `**Refuerzo:**`, `**Leccion:**`—, que es
   como están escritos en los 124 archivos de decisión de `books/` y como los
   cuenta la skill `automejora` con `grep '^\*\*Leccion:\*\*'`. El tablero
   tiene que leer lo mismo que cuenta el loop.

   **Y acepta además las variantes que existen de verdad**, porque existen: de
   los 124 archivos, tres traen `**Lección:**` con tilde y dos traen
   `**Donde (borrador):**` y `**Donde (plan):**`. El parser compara el nombre
   del marcador sin tildes y descarta el paréntesis. No es tolerancia gratuita:
   son archivos que un juez ya escribió y que el tablero no puede tirar, y la
   alternativa —enseñarlos como no entendidos— sería mentir sobre un veredicto
   que sí está claro en la primera línea.
3. **Lo que no case, se ignora en silencio y sobrevive en `crudo`.** Un juez que
   escriba un párrafo de más no puede romper la pantalla.
4. **Todo se lee como UTF-8, explícitamente.** Los archivos lo son; lo que está
   en cp1252 es la consola de Windows. Leer sin declarar la codificación
   convierte cada tilde en dos caracteres y se ve en pantalla.

---

## 4. El reloj del replay

**Los `mtime` no sirven.** Git no guarda fechas de modificación: en cualquier
máquina que haya clonado el repositorio, los veintidós archivos de
`decisiones/` de `adrian-2025` tienen la misma hora al segundo, la del
checkout. La spec del sistema dice que el "cuándo" está en la fecha del
archivo, y eso es cierto solo en la máquina donde corrió.

Así que el replay **no reconstruye tiempos: reconstruye el orden**, que sí es
determinista y sale de los nombres:

```
plan
└─ por cada capítulo, en orden
   └─ por cada intento, en orden
      ├─ el redactor escribe
      ├─ los dos jueces, a la vez
      ├─ las dos luces
      └─ aprobado, o vuelta al redactor
cierre
```

Cada acontecimiento tiene una **duración nominal**, pensada para que se lea en
pantalla, multiplicada por la velocidad elegida:

| Acontecimiento | ms |
|---|---|
| el plan | 2000 |
| el redactor escribe | 3000 |
| los jueces deliberan | 2500 |
| las luces caen | 600 |
| una roja abre su motivo | 4000 |
| el capítulo entra | 1200 |
| el cierre | 2500 |

A velocidad 1, `adrian-2025` —cinco capítulos, once intentos, seis con alguna
roja— dura **unos 110 segundos**. Es el número al que están ajustadas esas
duraciones: el vídeo de dos minutos de la spec funcional.

**El reloj real se enseña, pero no gobierna.** En pantalla aparece lo que la
novela tardó de verdad, de `sesion.json`; la animación corre a su propio ritmo.
Confundir las dos cosas sería fingir un directo, y eso está prohibido en §4 de
la funcional.

---

## 5. El servidor

Fino a propósito. Seis rutas.

| Ruta | Qué hace |
|---|---|
| `GET /api/novelas` | la lista, con slug, título, estado y coste |
| `GET /api/novelas/:slug` | el modelo entero de §3 |
| `GET /api/novelas/:slug/eventos` | SSE. Un evento por archivo que aparece o cambia. Con el slug reservado `_corriendo`, la novela que se esté escribiendo ahora, sea cual sea |
| `POST /api/novelas` | lanza una novela nueva |
| `DELETE /api/novelas` | para la corrida en marcha. No es un paso del ciclo: es cerrar el proceso que abrimos |
| `GET /api/salud` | si Claude Code está en el PATH y si `books/` se puede leer |

### El vigía

`chokidar` sobre `books/`. Cuando algo cambia, el servidor **relee la novela
entera y manda el modelo nuevo**. No manda parches ni lleva la cuenta de nada.

Releer entero es más caro y es deliberado: es la misma decisión que tomó el
sistema al no tener archivo de estado. Una novela son doscientos archivos de
texto; releerlos cuesta milisegundos, y a cambio el tablero **no puede
desincronizarse de la carpeta**, que es la única garantía que importa.

Los renombrados de aprobación (`mv NN.borrador.md NN.md`) llegan como un
borrado y una creación. El vigía no los interpreta: relee, y en el modelo nuevo
el capítulo ya está aprobado.

### El lanzador

```
POST /api/novelas  { idea: "..." }
```

Ejecuta **el mismo Claude Code que se usaría desde la terminal**, en la raíz del
repositorio, con la skill `dirigir-novela`:

```
claude -p "<idea>" --output-format stream-json --verbose
      --permission-mode acceptEdits
      --allowedTools Bash,Read,Write,Edit,Glob,Grep,Agent,Task
      --permission-prompts none
```

**Los permisos no son opcionales.** En modo `--print` no hay nadie a quien
preguntarle si puede escribir un archivo, así que sin declararlos todo lo que
necesita permiso se deniega solo: la corrida muere a los diez segundos sin
haber escrito nada y sin decir por qué. Las herramientas se nombran una por una
en vez de saltarse los permisos enteros, porque esto corre sobre el repositorio
de alguien y no en una caja de arena. Son las que pide la skill: `Bash` para
`mkdir`, `mv`, `sed`, `grep` y `wc`; `Read` y `Write` para los agentes; `Agent`
para despacharlos.

**Y tres cosas de Windows que rompen el lanzamiento, cada una por su cuenta:**

| | Qué pasa | Qué se hace |
|---|---|---|
| la entrada | con un tubo abierto que nadie escribe, Claude Code espera 3 s por si el prompt llega por ahí y se queja por la salida de error | `stdio: ['ignore', …]`: se cierra de entrada |
| los argumentos | con `shell: true`, Node concatena sin escapar, así que una idea con espacios llega partida en trozos y Claude recibe media frase como prompt y el resto como flags que no conoce | un `.exe` se lanza directo, sin shell; un `.cmd` se monta a mano y se pasa `windowsVerbatimArguments` |
| el primer minuto | Claude Code tarda cerca de un minuto en arrancar, leer la skill y despachar al arquitecto, y en ese rato no emite nada | el lanzador avisa a los suscriptores en cuanto arranca, sin esperar al stream |

**La idea va tal cual, y no lleva nada pegado.** Ni la longitud ni el slug. La
longitud viaja dentro de la propia idea porque es una instrucción para el
arquitecto, y la skill ya decide una novela corta si no se dice ninguna. El
slug lo elige la skill —«protagonista y año»—, así que el tablero no lo impone:
se entera mirando aparecer la carpeta (ver *el slug adoptado*, abajo).

- **El tablero no orquesta.** No despacha agentes, no lee luces y no renombra
  nada. Escribe un prompt y se aparta. Si el lanzador hiciera un solo paso del
  ciclo, la capa dejaría de ser una capa.
- **La verdad es el vigía, no el stream.** Todo lo que se pinta de la novela
  sale de los archivos. Del stream sale **una sola cosa**: qué agentes están
  encendidos en este segundo. Si el formato del stream cambia en una versión de
  Claude Code, se apagan los nodos y el resto del tablero sigue funcionando.

### Quién está trabajando ahora

Es lo único que la carpeta no puede contar: un agente despachado no deja rastro
en disco hasta que termina. Sale del `stream-json`, de dos eventos y nada más:

| Evento | Qué se hace |
|---|---|
| un `tool_use` con `input.subagent_type` | se enciende ese agente, con la `description` del despacho |
| el `tool_result` con ese `tool_use_id` | se apaga |

**Se mira `subagent_type`, no el nombre de la herramienta.** Atarlo a que la
herramienta se llame `Agent` lo rompe en cuanto cambie de nombre.

Y la `description` da gratis el capítulo y el intento, porque la skill
`dirigir-novela` obliga a escribirla así: `redactor · cap 03 · intento 2`. De
ahí salen el rótulo de la pantalla y la fila que se abre en la rejilla. Es el
mismo campo que Langfuse usa como nombre del subagente, así que no es un
formato que el tablero haya inventado para sí: ya era un contrato.

**Con los dos jueces a la vez, el rótulo los nombra juntos** —«revisor y
verificador · cap 01 · intento 2»—, no en fila. Escribirlos uno detrás de otro
sugeriría un orden que no existe.

### El slug adoptado

Cuando el vigía ve aparecer una carpeta en `books/` que no estaba y hay una
corrida en marcha, esa carpeta **es** la corrida. El tablero no elige el nombre
ni se lo pide a la skill: lo lee de la carpeta, que es la misma regla que
gobierna todo lo demás.

Mientras tanto la corrida existe sin slug, y por eso hay una suscripción de SSE
con el nombre reservado `_corriendo`: al lanzar todavía no hay novela a la que
suscribirse. Esa suscripción recibe el estado de la corrida y, en cuanto hay
carpeta, también el modelo de la novela.
- **En Windows, `claude` es un `.cmd`**, así que el `spawn` va con `shell: true`
  o resolviendo el ejecutable. Y conviene que `/api/salud` lo compruebe al
  arrancar: en esta máquina, sin ir más lejos, `git` no está en el `PATH` de
  PowerShell, y descubrir eso mientras se graba es una hora perdida.
- **Una corrida a la vez.** Dos novelas en paralelo escribiendo en `books/`
  hacen ilegible el vigía y no aportan nada.

### El modo estático, sin servidor

Para grabar no hace falta servidor: un script vuelca `books/` a un JSON y el
front lo importa. `npm run build` deja entonces una carpeta que se abre con
doble clic y reproduce cualquier corrida. Es el modo que se usa si el día de la
grabación algo falla, y el que permitiría enviar el tablero por un enlace sin
tocar una línea.

---

## 6. El diseño

### La paleta

La paleta es **la de Qaracter**, no una inventada para esto. El vídeo lo ven los
jefes de la casa, y el tablero tiene que parecer una herramienta de la casa.

La empresa la define en claro —fondo blanco, titulares en azul marino— y el
tablero es oscuro. Así que la paleta **se invierte, no se sustituye**: los dos
extremos intercambian su papel y los tres colores del medio se quedan donde
están.

| Corporativo | Hex | Qué es en el tablero |
|---|---|---|
| Fondo | `#FFFFFF` | el texto sobre fondo oscuro |
| Gris tarjeta | `#F5F5F5` | el papel del manuscrito |
| Azul titulares | `#1E2D3D` | la superficie de los paneles, y la tinta sobre el papel |
| Gris cuerpo | `#4A5763` | bordes y texto secundario |
| Naranja acento | `#F4631E` | el acento: lo que está vivo, y la luz roja |

De ahí salen los tokens, y de ningún otro sitio:

| Token | Hex | Para qué | De dónde sale |
|---|---|---|---|
| `--fondo` | `#131C26` | el fondo de la aplicación | el azul de titulares, oscurecido |
| `--superficie` | `#1E2D3D` | los paneles y la cabecera | azul titulares, tal cual |
| `--borde` | `#4A5763` | separadores, aristas en reposo, nodo inactivo | gris cuerpo, tal cual |
| `--papel` | `#F5F5F5` | el panel del manuscrito | gris tarjeta, tal cual |
| `--tinta` | `#1E2D3D` | el texto sobre papel | azul titulares, tal cual |
| `--tinta-suave` | `#4A5763` | el texto secundario sobre papel | gris cuerpo, tal cual |
| `--texto` | `#FFFFFF` | el texto sobre fondo y superficie | el blanco corporativo, invertido |
| `--texto-suave` | `#8FA0B0` | cifras y rótulos secundarios en oscuro | gris cuerpo, aclarado hasta que se lee sobre `--superficie` |
| `--naranja` | `#F4631E` | el acento, y la luz roja | naranja acento, tal cual |
| `--verde` | `#2F9E6B` | la luz verde | no es corporativo; el porqué está abajo |

**El azul marino ya no está prohibido.** La versión 1.0 decía *no azul marino,
que es el color de todos los dashboards*. Sigue siendo cierto que un azul frío
no distingue nada por sí solo, pero este azul no se eligió: es el de la empresa,
y quien vea el vídeo lo reconoce antes de leer una palabra. Lo que separa al
tablero de cualquier otro dashboard pasa a ser lo demás: el naranja, el papel y
la serif.

**El verde no es corporativo, y está bien que no lo sea.** La paleta de Qaracter
tiene cinco colores y ninguno es verde, porque es una paleta de marca y no de
estados. La luz verde necesita un verde: se usa uno apagado, a la luminancia
justa para que no compita con el naranja, y **no aparece en ningún otro sitio**
—ni en un botón, ni en un borde, ni en una barra de la cuenta—. Es el color de
una sola cosa.

**El naranja hace dos trabajos y no se confunden**, porque ocurren en sitios
distintos y con formas distintas:

| Dónde | Cómo | Qué significa |
|---|---|---|
| el nodo del agente | borde de 2 px, relleno `--superficie` | está corriendo ahora |
| la arista del grafo | el trazo que viaja | algo va por ahí |
| el círculo de la rejilla | anillo grueso, hueco | luz roja |
| el contador del coste | solo la cifra, monoespaciada | está subiendo |

Y una regla de cantidad: **nunca hay más de dos cosas naranjas a la vez en
pantalla**. Un acento repetido deja de ser un acento.

**El color nunca va solo.** Una luz verde es un círculo lleno y una roja es un
círculo hueco con un anillo grueso, y se distinguen en blanco y negro. El vídeo
puede acabar comprimido en una aplicación de mensajería, y dos colores a la
misma luminosidad se funden en el mismo gris. Con naranja y verde el riesgo es
mayor que antes, no menor: son justo los dos tonos que peor sobreviven a una
compresión agresiva.

### La marca

El logo está en el repositorio, en
`ui/web/src/diseno/marca/qaracter-negativo.png`, tal como lo entregó la empresa:
**la versión negativa**, isotipo naranja y "QARACTER" en blanco puro sobre
transparente. Es la que sirve en un tablero oscuro, y es la única que hay.

| Regla | Por qué |
|---|---|
| Aparece **una sola vez**, en la cabecera, arriba a la izquierda, y en las tres vistas | un logo repetido en cada panel es una marca de agua, no una marca |
| Nunca sobre `--papel` | el logotipo es blanco puro y desaparece sobre el gris claro |
| No se recolorea, no se estira, no se recorta, no se le añade nada | no es un elemento de la interfaz, es un archivo de otra persona |
| 24 px de alto en pantalla, 32 px en `modo grabación`, con un margen libre a los lados igual a esa altura | en el vídeo se ve a un tercio del tamaño y pegado a un borde no se lee |
| **El logo no entra en el panel del manuscrito** | la prosa la escribió un agente, no la empresa. Firmar un capítulo con el logo mezcla quién lo escribió con quién lo enseña, que es la distinción de la que viven las tres vistas |

**Los dos naranjas no se unifican.** El PNG del logo trae el isotipo en
`#FF7932` y la paleta dice `#F4631E`. Son distintos y se quedan distintos: el del
archivo es el logo y no se toca; el de la paleta es la interfaz. Retocar el PNG
para que casen sería editar la marca de la empresa para que encaje en una
demostración.

**No hay versión positiva** —logotipo en azul, para fondo claro— y mientras el
tema sea oscuro no hace falta. Si algún día se quiere una vista clara, se pide el
archivo: recolorear el blanco a mano no es la versión positiva, es una
aproximación con el nombre de la empresa dentro.

### El movimiento

Seis reglas, y la primera no es negociable:

1. **Los dos jueces se animan con el mismo retardo, cero diferencia.** Si uno
   entra veinte milisegundos antes, la pantalla está contando que hay un orden,
   y no lo hay. Es la regla 9 del sistema traducida a animación.
2. Nada dura más de 400 ms salvo lo que hay que leer.
3. Lo que aparece, entra desde donde vino: la luz cae desde su juez hasta la
   rejilla.
4. Lo que se repite, no se reanima: la rejilla de luces crece, no se redibuja.
5. Las aristas del grafo solo se animan cuando algo viaja por ellas.
6. Nada parpadea. Un tablero que parpadea parece que falla.

### La regla de la pantalla

**Ninguna vista tiene scroll.** El vídeo se graba a 1920×1080 y lo que no cabe
no existe. Si un capítulo es más largo que su panel, el panel hace scroll por
dentro y la página no.

Un `modo grabación` (tecla `G`) bloquea el ancho a 16:9, oculta la barra de
desarrollo y sube el tamaño base de la letra: lo que se lee cómodo en un
monitor a medio metro no se lee en un vídeo en un móvil.

### El teclado

Todo el recorrido se hace sin ratón, para que el vídeo salga de una toma y no
se vea el cursor buscando un botón.

| Tecla | |
|---|---|
| `1` `2` `3` | el círculo · el expediente · la cuenta |
| `4` | escribir una nueva |
| `espacio` | reproducir o pausar |
| `←` `→` | un acontecimiento atrás o adelante |
| `+` `−` | velocidad |
| `G` | modo grabación |

---

## 7. Convenciones

- **Código y comentarios en español, sin tildes**, igual que el resto del
  repositorio. Los textos de la interfaz sí llevan tildes: los lee una persona.
- **Nada de datos de ejemplo en el código.** Si una novela no tiene
  `sesion.json`, la pantalla dice "sin medir". Un dato inventado en una
  demostración es indistinguible de una mentira.
- **El lector es puro**: entra texto, sale modelo, sin tocar disco ni red. Es lo
  que permite probarlo con las corridas reales que ya están en `books/`.
- **Cada cambio de especificación se registra en el historial del documento que
  toca**, en la misma entrega, con qué cambió y por qué.

---

## 8. Qué hay construido y qué está comprobado

| Pieza | Construida | Comprobada |
|---|---|---|
| las tres vistas del historial | sí | sí, con capturas de las tres sobre `control-04` |
| la novela entera (`novela.md`) | sí | sí, se lee desde las dos pestañas |
| la pestaña de escribir | sí | sí, de punta a punta contra un Claude Code de mentira que emite el mismo `stream-json` |
| los agentes encendidos | sí | sí, los cuatro, con los dos jueces a la vez |
| el lector de `books/` | sí | sí, las 11 novelas y las 124 luces, 0 no entendidas |
| el reloj del replay | sí | sí, `control-04` dura 1m 17s y `adrian-2025` 1m 58s |
| el vigía y el SSE | sí | sí, renombrado, alta y baja de luces sobre una copia de `control-03` |
| el lanzador | sí | sí: una corrida falsa de punta a punta, y una de verdad hasta que el arquitecto escribió `plan.md` y el slug se adoptó solo (`farero-1962`, parada y borrada después). No se ha dejado terminar una novela entera |
| el modo estático | sí | sí, `dist/index.html` de 2,5 MB abierto desde `file://`, 0 errores |
| el logo en `diseno/marca/` | sí | sí, se lee en las tres vistas y en modo grabación |

**Lo que sí está comprobado antes de escribir una línea**, porque se miró en el
repositorio:

- Los `mtime` de `books/adrian-2025` son todos idénticos tras el clon, así que
  el orden tiene que salir de los nombres (§4).
- `sesion.json` existe en `control-01` a `control-06`, está **vacío** en
  `control-07` y **no existe** en `adrian-2025`, `ciclista-2010`,
  `veterano-2010` ni `sara-1994`. La vista de la cuenta se diseña con esa
  ausencia dentro, no como un error.
- `control-01/sesion.json` trae `total_cost_usd`, `modelUsage` por modelo con
  tokens de razonamiento, y `subagent_stats.by_type` con los 22 subagentes
  despachados. La vista de la cuenta no necesita nada más.
- Los archivos de decisión no llevan la hora dentro. La hora era el `mtime`. Y
  tampoco la trae `sesion.json`, así que **la fecha en que corrió una novela no
  existe en el repositorio**. La etiqueta del replay dice de dónde salen los
  archivos y no inventa una fecha.
- En Windows, si al vigía le llega una ruta en formato corto 8.3 —y este perfil
  de usuario tiene un punto en el nombre, así que la genera— libuv compara el
  nombre corto con el largo que devuelve el sistema de archivos, falla una
  aserción y **mata el proceso**: no es una excepción que se pueda capturar. El
  servidor normaliza la ruta con `realpathSync.native` antes de vigilarla.
- `duration_ms` de `sesion.json` es lo que tardó el último turno, no la corrida:
  en `control-01` son 14 segundos contra los 29 minutos de `duration_api_ms`.
  La vista de la cuenta usa el segundo.
- El PNG del logo es de 1406×331 con canal alfa: el fondo es transparente, el
  logotipo es blanco puro (`#FFFFFF`) y el isotipo es `#FF7932`, que **no** es el
  `#F4631E` de la paleta. Es la versión negativa y no hay otra, así que el tema
  oscuro no es solo una preferencia: es la condición para que el logo se lea.

Esta tabla se actualiza cuando cambie alguna de las dos columnas.

---

## 9. Historial técnico

| Versión | Fecha | Cambio | Por qué |
|---|---|---|---|
| **1.4** | 2026-09-20 | El lanzador declara permisos (`--permission-mode acceptEdits`, `--allowedTools`, `--permission-prompts none`), cierra la entrada estándar, deja de usar `shell: true` y avisa a los suscriptores nada más arrancar. Entra `DELETE /api/novelas` para parar una corrida. Un fallo se enseña entero, no recortado a una línea. | Las tres primeras eran fallos de verdad, encontrados lanzando: sin permisos declarados la corrida moría a los diez segundos sin escribir nada; con la entrada abierta, Claude Code esperaba tres segundos y se quejaba por la salida de error, y esa queja se enseñaba como si fuera el fallo; y con `shell: true` la idea llegaba partida en trozos, así que el prompt era media frase y el resto flags desconocidos. Lo del aviso al arrancar es que Claude Code tarda cerca de un minuto en despachar al arquitecto, y ese minuto en blanco parecía que el botón no había hecho nada. |
| **1.3** | 2026-09-20 | Dos pestañas. El lanzador recibe solo `{ idea }` y la manda tal cual: sin longitud pegada y sin slug. Del `stream-json` se saca qué agentes están encendidos, emparejando `tool_use` con `subagent_type` y su `tool_result`; la `description` del despacho da el capítulo y el intento. El slug se adopta al ver aparecer la carpeta, y hasta entonces se sigue la corrida por el nombre reservado `_corriendo`. `novela.md` se puede leer, en las dos pestañas. | Escribir una novela estaba metido en la barra de estado y no lo encontraba nadie. Los agentes encendidos son lo único de todo el tablero que no puede salir de la carpeta —un subagente despachado no deja rastro en disco hasta que acaba— y sin ellos esa pantalla son tres minutos mirando una carpeta vacía. El slug se adopta en vez de imponerse porque lo elige la skill, y pasárselo en el prompt habría sido el tablero diciéndole al orquestador cómo hacer su trabajo. |  Se corrige la regla 2 del parser: los cuatro marcadores van sin tilde, y el parser acepta además `**Lección:**` y `**Donde (…):**` porque están en archivos reales. Se actualiza §8 con lo que quedó comprobado. Entran tres hechos nuevos: la fecha de una corrida no existe en el repositorio, `duration_api_ms` es la duración de la corrida y `duration_ms` la del último turno, y en Windows una ruta en formato 8.3 mata el proceso del vigía. | La spec decía `**Dónde:**` y `**Qué cambiar:**` con tilde y ninguno de los 124 archivos de decisión los escribe así: con la regla literal, el tablero habría enseñado 66 rechazos sin su cita. Lo de la ruta 8.3 se encontró construyendo, y no es un fallo que se pueda capturar: aborta el proceso entero, así que tenía que quedar escrito antes de que le pase a otro. |
| **1.1** | 2026-09-20 | La paleta pasa a ser la corporativa de Qaracter, invertida para el tema oscuro: el azul de titulares es la superficie y la tinta, el gris de tarjeta es el papel, el blanco de fondo es el texto y el naranja es el acento y la luz roja. Se levanta la prohibición del azul marino de la 1.0. El verde de la luz queda fuera de la paleta, declarado como tal. Entra el apartado *La marca*, con el logo en `ui/web/src/diseno/marca/qaracter-negativo.png` y sus reglas de uso. | El vídeo lo ven los jefes de la empresa: un tablero con colores de nadie parece una demostración de internet y uno con la marca parece una herramienta de la casa. La paleta se invierte en vez de sustituirse porque la corporativa es clara y el tablero es oscuro, y porque el único logo que hay es el negativo —logotipo en blanco puro—, que sobre fondo claro desaparece. El verde se declara ajeno para que nadie lo busque en la guía de marca y acabe inventando un sexto color corporativo. |
| **1.0** | 2026-09-20 | Primera versión. `ui/web` y `ui/servidor`. React Flow para el grafo, Motion para el movimiento, Recharts para la cuenta, Fastify y chokidar en el servidor. El modelo sale entero de la carpeta y el vigía relee la novela completa en cada cambio. El replay reconstruye el orden desde los nombres de archivo, no desde los `mtime`. El lanzador invoca a Claude Code y no da un solo paso del ciclo. Dos familias tipográficas, una por origen del texto. | Los `mtime` no sobreviven a un clon, así que cualquier replay basado en fechas se rompe en la primera máquina que no sea la que corrió la novela. Releer entero en vez de aplicar parches repite la decisión que ya tomó el sistema al no tener archivo de estado: el tablero no puede desincronizarse de la carpeta. Y el lanzador se queda fuera del ciclo porque una UI que orquesta es exactamente la que se borró en `d42c084`. |
