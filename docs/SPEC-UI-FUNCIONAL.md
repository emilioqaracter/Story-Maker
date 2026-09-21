# Story-Maker — El tablero · Especificación funcional

**Versión 1.2** · 2026-09-20 · la parte técnica está en
[SPEC-UI-TECNICO.md](SPEC-UI-TECNICO.md). El sistema que escribe la novela está
descrito en [SPEC-FUNCIONAL.md](SPEC-FUNCIONAL.md); este documento no lo repite.

Este documento dice **qué enseña el tablero y por qué**: a quién se lo enseña,
qué tiene que entender esa persona, y qué no hace el tablero nunca.

---

## 1. Qué es esto

Una interfaz que **mira trabajar al sistema** y deja ver, sin abrir una sola
carpeta, lo que hoy solo se ve abriéndolas: quién está escribiendo, quién está
juzgando, qué se rechazó y con qué palabras, cuánto costó y qué acabó entrando
en el libro.

El sistema ya lo registra todo. El problema no es que falte información: es que
está en doscientos archivos Markdown repartidos en once carpetas, y nadie que
no haya construido esto va a leerlos.

> **El principio del que sale todo lo demás:** el tablero no decide nada. Solo
> enseña lo que los agentes ya decidieron, con sus palabras.

El tablero es la séptima capa, y como las otras seis **se puede apagar**.
Borrar `ui/` deja el sistema exactamente como está hoy: las novelas se siguen
escribiendo desde la terminal y las decisiones siguen enteras en disco.

---

## 2. Para quién es y qué tiene que entender

El destinatario es **alguien con criterio para decidir sobre el proyecto y sin
formación en IA**. No sabe qué es un agente, no ha visto una traza y no va a
leer una spec. Va a ver un vídeo de dos minutos.

Eso fija tres cosas.

**El entregable es una grabación, no una web.** Se ejecuta en local y se graba.
Nadie va a navegar el tablero por su cuenta, nadie lo va a abrir en un móvil y
nadie va a esperar a que cargue. A cambio, todo lo que aparezca tiene que
funcionar **en movimiento**: lo que no se anima, en un vídeo no existe.

**Tiene que entenderse sin voz en off.** Puede haber narración, pero la
grabación no puede depender de ella. Si alguien reenvía el vídeo sin contexto,
tiene que seguir contando lo mismo.

**Lo que tiene que quedar, en este orden:**

| | Lo que ve | Lo que entiende |
|---|---|---|
| 1 | Dos jueces que miran el mismo capítulo a la vez y sin hablarse, y una luz roja que lo devuelve con una cita textual | **Esto no se autoaprueba.** Hay un control de calidad y deja escrito por qué |
| 2 | La novela terminada, y detrás de cada capítulo su expediente entero | **Hay un producto real**, y es auditable hasta la frase |
| 3 | El coste desglosado, con el modelo caro solo donde se decide | **Esto está medido**, y se decidió dónde gastar |

Esas tres son las vistas del **historial**, en ese orden.

**Y hay una segunda pestaña, que no mira: pide.** El historial enseña corridas
que ya pasaron; *escribir una nueva* pide una novela y la mira nacer. Son dos
cosas distintas —una lee, la otra provoca— y al principio estaban mezcladas: el
campo para lanzar vivía en la barra de estado, junto al selector de novela, y
ahí no lo encontraba nadie. Un producto que se puede usar de dos maneras
distintas necesita decirlo en la primera pantalla, no esconder la mitad en un
rincón.

| | **Historial** | **Escribir una nueva** |
|---|---|---|
| Qué hace | lee `books/` | manda un prompt a Claude Code |
| Qué enseña | el círculo, la novela, la cuenta | los agentes encendidos, los capítulos según entran, y la novela final |
| De dónde sale | archivos que ya están | archivos según aparecen, más el stream |
| Para qué sirve | **grabar el vídeo** | enseñar que no hay truco |

**Y quien lo ve es de la casa.** El destinatario no es un cliente ni un
desconocido: es Qaracter. Así que el tablero lleva la marca de la empresa —el
logo en la cabecera y la paleta corporativa en toda la interfaz—, y no como
adorno. Un tablero con colores de nadie parece una demostración encontrada en
internet; uno con la marca parece una herramienta de la casa. Es la diferencia
entre *mira lo que se puede hacer* y *mira lo que tenemos*.

**Pero la marca se queda en el marco.** El logo va en la cabecera y en ningún
sitio más; los colores visten la aplicación y no el capítulo. El logo no firma
nunca un texto que escribió un agente. Esa frontera es la misma que sostiene las
tres vistas: la marca dice de quién es la herramienta, y lo que hay dentro es del
sistema, con sus palabras. Los colores exactos y las reglas del logo están en
[SPEC-UI-TECNICO.md](SPEC-UI-TECNICO.md).

**Lo que se queda fuera, a propósito.** El loop de
[automejora](SPEC-AUTOMEJORA-FUNCIONAL.md) —siete novelas, reglas que nacen de
las lecciones de los jueces, unas que se quedan y otras que se revierten— es
probablemente lo más difícil de ver en cualquier otra herramienta, y no entra
en esta versión porque no se pidió. La bitácora ya tiene los datos, así que
añadir esa vista después es trabajo de un día y no obliga a rehacer nada.

---

## 3. Las tres vistas

En los esquemas, `[Q]` es el logo de Qaracter. La cabecera es la misma en las
tres vistas y el logo ocupa siempre el mismo punto: al pasar de una vista a otra
no se mueve, y el recorrido entero del vídeo queda cosido por él.

### 3.1 El círculo

La pantalla principal. El ciclo de aprobación de un capítulo, en marcha.

```
┌─ [Q] STORY-MAKER ───────────────────────────── adrian-2025 ─ cap 03 · intento 2 ─┐
│                                                                                  │
│                                             ┌─────────────────────────────────┐  │
│        ┌────────────┐                       │  cap  int   REV   VER           │  │
│        │ ARQUITECTO │ ✓                     │   01   1     ●     ●            │  │
│        └────────────┘                       │   01   2     ○     ○   aprobado │  │
│              │                              │   02   1     ●     ○            │  │
│              ▼                              │   02   2     ○     ○   aprobado │  │
│        ┌────────────┐                       │   03   1     ○     ●            │  │
│    ┌──►│  REDACTOR  │───┬──► ┌──────────┐   │   03   2    ...   ...           │  │
│    │   └────────────┘   │    │ REVISOR  │   │                                 │  │
│    │                    │    └──────────┘   ├─────────────────────────────────┤  │
│    │                    │    ┌──────────┐   │  ● ROJA · verificador · cap 03  │  │
│    │                    └──► │VERIFICADR│   │                                 │  │
│    │                         └──────────┘   │  «Marta ya sabía que el equipo  │  │
│    │                              │         │   la iba a dejar fuera.»        │  │
│    └──── alguna roja ─────────────┘         │                                 │  │
│                                             │  Qué cambiar: la decisión se    │  │
│   ▓▓▓▓▓▓▓▓░░░░░  3 de 5 capítulos           │  comunica en el capítulo 7...   │  │
│   1,42 USD · 6m 20s · 14 despachos          └─────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

Lo que tiene que pasar en esta pantalla, por orden de importancia:

1. **Los dos jueces se encienden a la vez.** Es la imagen que explica el
   sistema entero. Si se encendieran uno después del otro, la pantalla estaría
   contando una mentira sobre cómo funciona.
2. **La luz cae y se ve de qué color es**, en la rejilla de la derecha, que va
   creciendo hacia abajo. Al final de la novela esa rejilla **es** el contenido
   de `decisiones/`, y se lee de un vistazo: dónde costó, quién rechazó más.
3. **Una luz roja abre su motivo**, con la cita textual del capítulo y el qué
   cambiar. Esto es lo que separa este sistema de un filtro automático: el
   rechazo está argumentado y se puede discutir.
4. **El capítulo vuelve al redactor** y el ciclo se repite. Ver rebotar un
   capítulo es ver el control funcionando.
5. **El coste sube mientras tanto.** Un número que crece solo hace que lo demás
   parezca real.

**Lo que no se enseña.** El motivo de una luz verde no se abre solo: ocupa lo
mismo que una roja y no cuenta nada. Se abre si se pide.

### 3.2 El expediente

La novela terminada, leíble, y al lado la historia de cada capítulo.

```
┌─ [Q] LA NOVELA ──────────────────── adrian-2025 · 5 capítulos · 11 intentos ────┐
│                                        │                                        │
│  Capítulo 3                            │  ● ROJA   verificador · intento 1      │
│  ───────────                           │    El protagonista sabe algo que       │
│                                        │    todavía no ha pasado                │
│  La cancha se heló bajo sus pies       │    «Marta ya sabía que el equipo...»   │
│  cuando oyó el nombre. Marc Puig.      │                                        │
│  Y supo, antes de poder pensarlo,      │  ○ VERDE  revisor    · intento 1       │
│  que aquel chaval de hombros anchos    │                                        │
│  tenía los ojos de Ricard.             │  ─────────────────────────────────     │
│                                        │                                        │
│  Dejó caer la pelota. La oyó botar     │  ○ VERDE  revisor    · intento 2       │
│  dos veces y rodar hasta la línea      │  ○ VERDE  verificador · intento 2      │
│  de fondo, y no fue a buscarla.        │    ✓ el capítulo entra                 │
│                                        │                                        │
│  [ 459 palabras · 2 intentos ]         │  Lo que este capítulo deja fijado:     │
│                                        │  · Marc Puig, 23 años, de Vinaroz      │
│  ◄ cap 2          cap 4 ►              │  · Ricard murió en 1987, Salvador...   │
└────────────────────────────────────────┴────────────────────────────────────────┘
```

**El capítulo se lee como un libro y se audita como un expediente.** A la
izquierda, prosa con tipografía de libro. A la derecha, todos los juicios que
recibió, en orden, con sus motivos, y al final los hechos que el verificador
dejó anotados en `continuidad/`.

**Y la novela entera se lee aquí también.** `novela.md` —el libro cerrado, con
su título y sus capítulos seguidos— se abre desde el pie del manuscrito, y
entonces el panel de la derecha cambia a un índice: cuántas palabras tiene cada
capítulo, cuántos intentos costó y cuántos rechazos llevó. Es la respuesta a
*«¿y dónde está lo que escribió?»*, que es la primera pregunta que hace
cualquiera que mire esto.

### 3.2 bis · Escribir una nueva

```
┌─ [Q] STORY-MAKER ── historial · ESCRIBIR ─── migue-2011 · escribiendo ─ EN VIVO ─┐
│ «Un boxeador de Vallecas al que le queda un combate. Dos capítulos de unas 400.» │
│ 4s  revisor y verificador · cap 01 · intento 2      │ cap 01 …  cap 02 …        │
│                                                     ├───────────────────────────┤
│        ┌────────────┐                               │                           │
│        │ ARQUITECTO │ ✓                             │   todavía no hay nada     │
│        └─────┬──────┘        ┌──────────┐           │   escrito. El primer      │
│              ▼          ┌───►│ REVISOR  │ ◄ naranja │   capítulo aparecerá      │
│        ┌────────────┐   │    └──────────┘           │   aquí en cuanto pase     │
│        │  REDACTOR  │───┤    ┌──────────┐           │   las dos luces.          │
│        └────────────┘   └───►│VERIFICADR│ ◄ naranja │                           │
│  cap int REV VER                                    │                           │
│   01  1   ●   ○                                     │                           │
│   01  2  ...  ...                                   │                           │
└─────────────────────────────────────────────────────┴───────────────────────────┘
```

**Se pide con una frase, y la longitud va dentro de la frase.** No hay una
casilla de «palabras» al lado del prompt. La longitud es una instrucción para
el arquitecto, no un parámetro del tablero: cabe decir *«tres capítulos de unas
700 palabras»* y cabe decir *«algo corto, que se lea de una sentada»*, y la
skill ya sabe qué hacer si no se dice nada. Una casilla numérica obligaba a
contestar una pregunta que a veces no tiene respuesta, y partía en dos lo que
el usuario quiere decir de una vez.

**Los agentes se encienden de verdad.** Un agente despachado no deja rastro en
disco hasta que termina, así que esto es lo único de todo el tablero que no sale
de la carpeta: sale del stream de Claude Code. Y es lo único que justifica esta
pantalla, porque sin ello el usuario mira una carpeta vacía durante tres
minutos y se va.

**Lo que va apareciendo se abre solo.** Cada capítulo aparece en cuanto pasa las
dos luces, y se abre para leerlo sin tocar nada. Al final aparece la novela
entera. Si el usuario elige un capítulo a mano, el tablero deja de cambiárselo
de delante.

**Un aviso sobre lo que no se puede enseñar.** El sistema no guarda los
borradores rechazados: `03.borrador.md` se renombra a `03.md` y la versión
anterior desaparece. No hay, por tanto, un antes y un después del capítulo. Lo
único que sobrevive del texto rechazado es **la cita dentro de la luz roja**, y
por eso la cita se muestra siempre entre comillas y con el aspecto de lo que
es: un fragmento de un texto que ya no existe. Si algún día se quisiera enseñar
el antes y el después, habría que conservar los borradores, y eso es un cambio
del sistema, no del tablero.

### 3.3 La cuenta

Lo que costó, y dónde se fue.

```
┌─ [Q] LA CUENTA ───────────────────────────────────────── control-01 · 3 caps ────┐
│                                                                                  │
│   3,57 USD          29 min          22 subagentes        0 fallos                │
│                                                                                  │
│   Dónde se fue el dinero                                                         │
│   ┌──────────────────────────────────────────────────────────────────────┐       │
│   │ sonnet   los que juzgan    ████████████████████████████████  3,20 USD│       │
│   │ haiku    los que escriben  ███                               0,37 USD│       │
│   └──────────────────────────────────────────────────────────────────────┘       │
│                                                                                  │
│   Quién trabajó                     Novela         Coste    Caps   A la primera  │
│   arquitecto    1                   control-01    3,57 €      3         0        │
│   redactor      7                   control-03    ...         3         2        │
│   revisor       7                   control-05    ...         3         1        │
│   verificador   7                   control-06    ...         3         1        │
└──────────────────────────────────────────────────────────────────────────────────┘
```

**El argumento de esta pantalla es uno solo:** el 90 % del dinero se va en los
dos agentes que deciden, y el 10 % en los que ejecutan. Eso no es un accidente,
está en la spec y se puede leer en los números. Para alguien que aprueba
presupuestos, es la pantalla que dice que aquí hubo criterio de ingeniería.

**De dónde salen los números.** De `sesion.json`, que Claude Code deja en la
carpeta de la novela con el coste real desglosado por modelo, los tokens, los
tokens de razonamiento y el recuento de subagentes despachados. No se estima
nada y no se llama a ninguna API.

**Lo que falta, se dice que falta.** Las novelas anteriores a las de control no
tienen `sesion.json`, y `control-07` lo tiene vacío porque se interrumpió a
mano. Esas novelas aparecen con el coste **sin medir**, no con un cero ni con
una estimación. Un número inventado en esta pantalla se lleva por delante la
credibilidad de las otras dos.

---

## 4. Los dos modos

El tablero hace lo mismo en los dos casos; lo único que cambia es de dónde
vienen los acontecimientos.

| | **Replay** | **En vivo** |
|---|---|---|
| Qué enseña | una novela que ya se escribió | una novela escribiéndose ahora |
| De dónde sale | los archivos de `books/<slug>/` | los mismos archivos, según aparecen |
| Cuánto dura | lo que se le diga: 90 segundos o 10 minutos | lo que tarde: entre 15 y 25 minutos |
| Para qué sirve | **grabar el vídeo** | enseñar que no hay truco |

**El replay es el modo de trabajo, no un sustituto.** Una novela real tarda
veinte minutos y cuesta tres dólares, y ninguna de las dos cosas cabe en una
grabación de dos minutos. El replay reproduce una corrida **real** —las luces
son las que dieron los jueces, las citas son las suyas, el coste es el que
costó— a la velocidad que haga falta.

**Y el modo en vivo existe para que el replay sea creíble.** Poder escribir una
idea, darle a un botón y ver arrancar el mismo tablero con una novela que no
existía es lo que demuestra que lo anterior no era un vídeo pregrabado. Basta
con que aparezca al final de la grabación, treinta segundos, con el primer
capítulo en marcha.

**El replay nunca se disfraza de directo.** Lleva su etiqueta en pantalla, con
el nombre de la novela y la fecha en que corrió. Enseñar una grabación diciendo
que es tiempo real es exactamente el tipo de cosa que destruye la confianza que
las otras tres pantallas intentan construir.

---

## 5. Lo que el tablero no hace nunca

1. **No decide si un capítulo está bien.** No aprueba, no rechaza y no sugiere.
   Esa regla es del sistema y el tablero es parte del sistema.
2. **No interpreta una luz que no entiende.** Si la primera línea de un archivo
   de decisión no es `LUZ: VERDE` ni `LUZ: ROJA`, el tablero enseña el archivo
   en crudo y lo marca como no entendido. No deduce el veredicto. Es la misma
   regla que tiene la sesión que orquesta, y por el mismo motivo: deducirlo
   sería decidir.
3. **No resume ni reescribe un motivo.** La cita y el qué cambiar se muestran
   tal como los escribió el juez. Se pueden recortar por espacio, nunca
   reformular.
4. **No guarda estado propio.** No tiene base de datos ni caché persistente. El
   estado sigue siendo la carpeta. Si el tablero y la carpeta discrepan, el que
   está mal es el tablero.
5. **No toca `books/` ni `.claude/`.** Lee. En modo en vivo lanza a Claude
   Code, y es Claude Code quien escribe, igual que desde la terminal.
6. **No inventa un número.** Lo que no está medido se enseña como no medido.
7. **No firma con la marca lo que escribió un agente.** El logo vive en la
   cabecera. No entra en el panel del manuscrito, no acompaña a una cita y no
   aparece junto a la luz de un juez. Quien enseña el trabajo y quien lo hizo no
   son lo mismo, y el tablero no puede sugerir que sí.

---

## 6. Por qué esto no rompe el principio de que no hay código

El repositorio dice, en su primera línea técnica, que no hay ni un script. Este
documento propone añadir una aplicación entera. Conviene decir por qué eso no
es una contradicción, sobre todo porque **ya pasó una vez**: en `d42c084` se
borró una UI de React con su servidor de Python, y el motivo está escrito en el
commit: *el criterio de aceptación vivía en validadores de Python opacos*.

La diferencia es exactamente esa. Aquellos scripts —`validate_scene`,
`gate_scene`— **decidían si una escena pasaba**. El tablero no decide nada: lee
archivos que ya contienen las decisiones y los dibuja.

De ahí salen las cuatro condiciones que hacen que esta capa se pueda añadir sin
tocar el principio, y que son las que hay que comprobar en cualquier cambio
futuro:

| Condición | Cómo se comprueba |
|---|---|
| El criterio sigue en los agentes | no hay una sola condición sobre la calidad de un capítulo en todo `ui/` |
| El estado sigue en la carpeta | apagar el tablero a media novela no pierde nada; la sesión sigue por donde iba |
| El orquestador sigue siendo Claude Code | lanzar desde el tablero ejecuta la misma skill `dirigir-novela`, sin pasos propios |
| La capa se puede apagar | borrar `ui/` deja el repositorio funcionando como hoy |

Y una prueba más dura que las cuatro: **el tablero no puede ser necesario para
nada**. El día que alguien tenga que abrirlo para saber cómo va una novela, la
capa habrá dejado de ser una capa.

### La tabla de capas, con la séptima

| Capa | Qué aporta | Qué pasa si se apaga |
|---|---|---|
| el plan | arquitecto y redactor | no hay novela |
| las decisiones en disco | qué se decidió y por qué | escribe a ciegas |
| el revisor | luz roja por cómo está escrito | entra todo |
| el verificador | luz roja por coherencia | los capítulos se contradicen |
| el director | el turno lo decide un agente | se decide leyendo la carpeta |
| Langfuse | tiempos, costes y comparar corridas | las decisiones siguen enteras |
| **el tablero** | **verlo sin abrir una carpeta** | **se abre la carpeta** |

---

## 7. Cuándo está terminado

No cuando compile. El tablero está terminado cuando se cumple esto:

- Se graba un vídeo de **dos minutos, sin voz**, y alguien que no sabe qué es
  un agente puede decir después, con sus palabras, que hay dos revisores
  independientes, que un texto puede ser rechazado con un motivo escrito, y que
  eso cuesta dinero y está medido.
- El vídeo se puede grabar **de una sola toma**, sin cortes de montaje: el
  recorrido entre las tres vistas se hace con el teclado y ninguna pantalla
  necesita scroll.
- Se lanza una novela nueva desde el tablero y el primer capítulo aparece solo,
  sin refrescar nada.
- Se borra `ui/` y una novela se escribe desde la terminal como el primer día.
- Se congela un fotograma cualquiera del vídeo, se mira en un móvil, y el logo
  se lee y se distingue una luz verde de una roja. Si a ese tamaño el logotipo
  se empasta o las dos luces son el mismo gris, la marca y el color están puestos
  para el monitor y no para el entregable.

---

## 8. Historial

| Versión | Fecha | Cambio | Por qué |
|---|---|---|---|
| **1.2** | 2026-09-20 | Dos pestañas: *historial*, con las tres vistas de antes, y *escribir una nueva*, donde se pide una novela, se ven encenderse los agentes que trabajan en cada momento, van apareciendo los capítulos según entran y al final aparece la novela entera. Desaparece la casilla de palabras: la longitud va dentro del prompt. Y `novela.md` se puede leer, también desde el historial. | Escribir una novela vivía en un campo de texto dentro de la barra de estado, así que la mitad del producto no la encontraba nadie: lo que se veía era el historial y se entendía que el tablero solo servía para mirar atrás. Y `novela.md` se leía del disco desde la primera versión pero no se enseñaba en ninguna parte, que es un sitio raro donde esconder el producto. La casilla de palabras se va porque partía en dos lo que el usuario dice de una vez, y porque obligaba a poner un número incluso cuando la respuesta honesta es «algo corto». |
| **1.1** | 2026-09-20 | El tablero lleva la marca de Qaracter: el logo en la cabecera de las tres vistas y la paleta corporativa en toda la interfaz. Entra la regla de que la marca se queda en el marco y nunca firma un capítulo, como séptimo "lo que no hace nunca". Y una condición más de terminado: el logo y las dos luces tienen que aguantar un fotograma congelado visto en un móvil. | El destinatario del vídeo es la propia empresa. Un tablero con colores de nadie se ve como una demostración encontrada por ahí, y uno con la marca se ve como una herramienta de la casa: cambia lo que la misma imagen significa para quien decide. La frontera —marca fuera, prosa dentro— no es estética: el tablero existe para enseñar que las decisiones son de los agentes, y un logo junto a una cita diría lo contrario. |
| **1.0** | 2026-09-20 | Primera versión. Tres vistas: el círculo, el expediente y la cuenta. Dos modos, replay y en vivo. El tablero como séptima capa apagable, con las cuatro condiciones que la separan de la UI borrada en `d42c084`. El entregable es una grabación. | El sistema registra todo y nada de eso se ve sin abrir once carpetas. El destinatario no sabe de IA y no va a leer una spec, así que la unidad de entrega es un vídeo de dos minutos y eso manda sobre el diseño: lo que no se anima no existe. El loop de automejora se deja fuera porque no se pidió, no porque no valga. |
