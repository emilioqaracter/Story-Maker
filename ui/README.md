# El tablero

La interfaz que mira trabajar al sistema. Lee `books/`, dibuja lo que encuentra
y no decide nada.

Tiene dos pestañas:

- **historial** — corridas que ya pasaron. Se reproducen, se auditan hasta la
  cita y se cuenta lo que costaron. Es la pestaña que se graba.
- **escribir una nueva** — se pide una novela con una frase, se ven encenderse
  los agentes que trabajan en cada momento, van apareciendo los capítulos según
  pasan las dos luces, y al final aparece la novela entera. Necesita el
  servidor.

La longitud de la novela **va dentro de la frase que escribes**, no en una
casilla aparte: es una instrucción para el arquitecto.

El qué y el porqué están en [SPEC-UI-FUNCIONAL.md](../docs/SPEC-UI-FUNCIONAL.md);
el cómo, en [SPEC-UI-TECNICO.md](../docs/SPEC-UI-TECNICO.md). Esto es solo cómo
se arranca.

> Se puede borrar `ui/` entero y el sistema sigue igual: las novelas se escriben
> desde la terminal y las decisiones siguen enteras en disco.

## Lo que hace falta

**Node 22.18 o posterior.** El servidor y las herramientas son TypeScript que se
ejecuta sin compilar, con el borrado de tipos que Node trae de serie desde esa
versión. No hay paso de build para el servidor.

```
npm install
```

## Arrancar

```
npm run dev
```

Levanta las dos mitades: el servidor en `127.0.0.1:4317` y el front en
`127.0.0.1:5173`. Abre el segundo.

## Grabar

Para grabar no hace falta servidor:

```
npm run build
```

Vuelca `books/` a un JSON, lo mete dentro del HTML y deja
`web/dist/index.html`: **un solo archivo que se abre con doble clic** y
reproduce cualquier corrida, sin red y sin nada instalado. Es el modo que se usa
si el día de la grabación algo falla, y el que permite enviar el tablero por un
enlace.

Una vez abierto, la tecla `G` entra en modo grabación: bloquea la pantalla a
16:9, sube el tamaño de la letra y esconde la barra de desarrollo.

## El teclado

Todo el recorrido se hace sin ratón, para que el vídeo salga de una toma.

| Tecla | |
|---|---|
| `1` `2` `3` | historial: el círculo · la novela · la cuenta |
| `4` | escribir una nueva |
| `espacio` | reproducir o pausar |
| `←` `→` | un acontecimiento atrás o adelante; en la novela, de capítulo |
| `+` `−` | velocidad |
| `G` | modo grabación |
| `C` | en la novela, el archivo de decisión tal como está en disco |

## Tres cosas que conviene saber antes de grabar

**El tablero se abre por una novela que esté medida.** Elige la que más intentos
tenga de entre las que tienen `sesion.json`, hoy `control-04`: 4,36 USD, 3
capítulos, 8 intentos. `adrian-2025` es la corrida más larga —5 capítulos, 11
intentos, 1m 58s de replay— pero **no tiene `sesion.json`**, así que su coste
sale como *sin medir* y la vista de la cuenta se queda vacía. Si se quiere
grabar con ella, hay que volver a correrla para que deje su `sesion.json`.

**El modo en vivo necesita encontrar Claude Code.** Si `claude` no está en el
`PATH` —en esta máquina no lo está: vive dentro de la extensión de VS Code—, hay
que decírselo:

```
$env:STORY_MAKER_CLAUDE = "C:\ruta\a\claude.exe"
npm run dev
```

`GET /api/salud` lo dice al arrancar, y el servidor lo imprime en su primera
línea. Descubrirlo mientras se graba es una hora perdida.

**El replay lleva su etiqueta y no se la quita.** Dice que es un replay y de
dónde salen los archivos. La fecha en que corrió la novela no aparece porque no
existe: no está dentro de los archivos de decisión, no está en `sesion.json`, y
los `mtime` no sobreviven a un clon.

## Herramientas

| | |
|---|---|
| `npm run comprobar` | pasa el lector por todas las novelas de `books/` y cuenta luces, intentos y cuáles no se entendieron |
| `npm run volcar` | regenera el volcado que usa el modo estático |
| `npm run tipos` | comprueba los tipos del front |

`npm run comprobar` es la prueba que importa: no usa datos de ejemplo, usa las
corridas reales.

## Dónde está cada cosa

```
web/src/
  vistas/     el-circulo, el-expediente, la-cuenta
  piezas/     nodos del grafo, la rejilla de luces, la tarjeta de luz
  reloj/      el guion del replay y su store
  lector/     de archivos a modelo. Puro: entra texto, sale modelo
  diseno/     los tokens de color y el logo de Qaracter
servidor/src/
  lector/     la unica parte que toca disco
  vigia/      chokidar sobre books/
  lanzador/   invoca a Claude Code y se aparta
```

`books/` y `.claude/` no se tocan. El tablero no escribe un solo byte dentro de
ninguna de las dos.
