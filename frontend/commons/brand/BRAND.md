# Marca de la empresa para el frontend

Todo lo que la rama `main` especificaba sobre la marca, reunido en un sitio para diseñar `frontend/`. Sale de `docs/SPEC-UI-TECNICO.md` §6, `docs/SPEC-UI-FUNCIONAL.md` §2 y §3 y `ui/web/src/diseno/` de esa rama. Aquel frontend era un tablero oscuro, pensado para grabar un vídeo. Este es una aplicación de lectura con tema claro y oscuro. Por eso la última sección dice qué se puede usar tal cual y qué hay que decidir.

| Fichero | Qué es |
|---|---|
| `logo-negativo.png` | El logo tal como lo entregó la empresa, copiado byte a byte |
| `tokens.css` | Los cinco colores corporativos y los tokens del tablero de `main`, en propiedades CSS. Lo importa `commons/shell/style.css` |
| `Marca.tsx` | Componente `<Marca alto={24} />` que pinta el logo con su margen libre. Lo monta la cabecera, `commons/shell/Layout.tsx` |

---

## 1. La paleta corporativa

Son cinco colores. La empresa los define en claro: fondo blanco y titulares en azul marino. **No hay un sexto color corporativo.**

| Corporativo | Hex | Token |
|---|---|---|
| Fondo | `#FFFFFF` | `--marca-fondo` |
| Gris tarjeta | `#F5F5F5` | `--marca-gris-tarjeta` |
| Azul titulares | `#1E2D3D` | `--marca-azul-titulares` |
| Gris cuerpo | `#4A5763` | `--marca-gris-cuerpo` |
| Naranja acento | `#F4631E` | `--marca-naranja-acento` |

### Cómo se pasó a tema oscuro en `main`

La paleta **se invierte, no se sustituye**. Los dos extremos intercambian su papel y los tres colores del medio se quedan donde están. Los tokens salen de ahí y de ningún otro sitio:

| Token | Hex | Para qué | De dónde sale |
|---|---|---|---|
| `--color-fondo` | `#131C26` | Fondo de la aplicación | Azul titulares, oscurecido |
| `--color-superficie` | `#1E2D3D` | Paneles y cabecera | Azul titulares, tal cual |
| `--color-superficie-alta` | `#26384A` | Superficie elevada | Azul titulares, aclarado |
| `--color-borde` | `#4A5763` | Separadores, aristas en reposo, elementos inactivos | Gris cuerpo, tal cual |
| `--color-papel` | `#F5F5F5` | Panel del manuscrito | Gris tarjeta, tal cual |
| `--color-papel-alto` | `#FFFFFF` | La hoja del capítulo | Blanco corporativo |
| `--color-tinta` | `#1E2D3D` | Texto sobre papel | Azul titulares, tal cual |
| `--color-tinta-suave` | `#4A5763` | Texto secundario sobre papel | Gris cuerpo, tal cual |
| `--color-texto` | `#FFFFFF` | Texto sobre fondo y superficie | Blanco corporativo, invertido |
| `--color-texto-suave` | `#8FA0B0` | Cifras y rótulos secundarios en oscuro | Gris cuerpo, aclarado hasta que se lee sobre la superficie |
| `--color-naranja` | `#F4631E` | Acento y estado de fallo | Naranja acento, tal cual |
| `--color-verde` | `#2F9E6B` | Estado de éxito | **No es corporativo** |

### Reglas de color

- **El verde no es corporativo, y está bien que no lo sea.** Es una paleta de marca, no de estados. El verde se usa apagado, con la luminancia justa para no competir con el naranja, y **solo para el estado de éxito**: ni botones, ni bordes, ni barras de gráficas. Es el color de una sola cosa. Se declara ajeno para que nadie lo busque en la guía de marca y acabe inventando un sexto color corporativo.
- **Nunca hay más de dos cosas naranjas a la vez en pantalla.** Un acento repetido deja de ser un acento.
- **El naranja hace varios trabajos y no se confunden**, porque cada uno tiene su sitio y su forma. En `main`: un borde de 2 px significaba «está corriendo ahora»; un trazo que viaja, «algo va por aquí»; un anillo grueso y hueco, fallo; una cifra monoespaciada, «está subiendo».
- **El color nunca va solo.** El éxito era un círculo lleno y el fallo un círculo hueco con anillo grueso, para que se distingan en blanco y negro. Naranja y verde son justo los dos tonos que peor sobreviven a una compresión agresiva.
- **El azul marino está permitido** porque es el de la empresa y se reconoce antes de leer una palabra. Lo que distingue la interfaz de un dashboard cualquiera es lo demás: el naranja, el papel y la serif.

---

## 2. El logo

`logo-negativo.png`: 1406×331 px con canal alfa. Fondo transparente, logotipo en blanco puro (`#FFFFFF`) e isotipo en `#FF7932`. **Es la versión negativa y la única que hay.**

| Regla | Por qué |
|---|---|
| Aparece **una sola vez**, en la cabecera, arriba a la izquierda, y en el mismo punto en todas las vistas | Un logo repetido en cada panel es una marca de agua, no una marca. Al cambiar de vista no se mueve |
| **Nunca sobre fondo claro** (`--color-papel`, blanco o gris tarjeta) | El logotipo es blanco puro y desaparece |
| No se recolorea, no se estira, no se recorta, no se le añade nada | No es un elemento de la interfaz, es un archivo de otra persona |
| 24 px de alto normalmente, 32 px en modo grande, con un margen libre a los lados igual a esa altura | Pegado a un borde o a tamaño pequeño no se lee |
| **No entra en el manuscrito** ni acompaña a una cita o a un veredicto | La prosa la escribió un agente, no la empresa. El logo dice de quién es la herramienta; lo que hay dentro es del sistema |

**Los dos naranjas no se unifican.** El isotipo del PNG es `#FF7932` y la paleta dice `#F4631E`. El del archivo es el logo y no se toca; el de la paleta es la interfaz.

**No hay versión positiva**, con el logotipo en azul para fondo claro. Si hace falta, se pide el archivo a la empresa. Recolorear el blanco a mano no es la versión positiva: es una aproximación con el nombre de la empresa dentro.

**La marca se queda en el marco.** Los colores visten la aplicación, no el capítulo.

---

## 3. Tipografía

Las tipografías forman parte de la arquitectura, no del adorno. Son dos familias, y la regla se rompe si se usa una sola:

| Token | Familia | Para qué |
|---|---|---|
| `--font-libro` | **Literata**, o Source Serif 4; respaldo Georgia | Todo lo que escribió un agente: prosa del capítulo, motivo de un veredicto, citas |
| `--font-maquina` | **JetBrains Mono**; respaldo `ui-monospace`, Cascadia Mono | Todo lo que midió la máquina: costes, tokens, contadores, nombres de archivo, relojes |

Nunca al revés. Quien lee aprende la regla en diez segundos sin que nadie se la diga, y a partir de ahí sabe qué está mirando por la forma de la letra.

En `main` las fuentes no se cargaban: se nombraban y caía la de respaldo. Si se quieren de verdad, hay que servirlas.

Formato de cifras de `main` (`diseno/formato.ts`): locale `es-ES`, importes con dos decimales, tokens en miles («114k»), y lo que no está medido se muestra como «sin medir», nunca como cero.

---

## 4. Movimiento

| Regla | |
|---|---|
| Entrada estándar | `--animate-entra`: 320 ms, `cubic-bezier(0.2, 0, 0, 1)`, desde 4 px más abajo y opacidad 0 |
| Duración máxima | Nada dura más de 400 ms salvo lo que hay que leer |
| Lo simultáneo entra a la vez | Si dos cosas son iguales, se animan con el mismo retardo; una diferencia de 20 ms ya sugiere un orden que no existe |
| Origen | Lo que aparece entra desde donde vino |
| Lo que se repite no se reanima | Una lista crece; no se redibuja |
| Nada parpadea | Una interfaz que parpadea parece que falla |

---

## 5. Cómo la aplica el frontend

`commons/shell/style.css` importa `tokens.css` y da a cada token un papel en la interfaz (`--bg`, `--heading`, `--accent`…), en claro y en oscuro por `prefers-color-scheme`. No usa Tailwind. `commons/ui/contrast.test.ts` comprueba el contraste AA de cada par en los dos temas. Así queda cada punto:

| Punto | Situación | Cómo queda |
|---|---|---|
| Tema claro | La paleta corporativa es clara y se usa tal cual: blanco de fondo, azul en titulares, gris cuerpo en texto, naranja de acento | Directo |
| Tema oscuro | La inversión de §1 ya está hecha y probada | Directo |
| **Logo en tema claro** | Solo existe la versión negativa, que sobre blanco desaparece | La cabecera va siempre en `--marca-azul-titulares`, también en tema claro. Si algún día hace falta el logo sobre claro, se pide a la empresa la versión positiva. No se recolorea |
| Estados de la tirada | Éxito en `--color-verde` y fallo en `--color-naranja`, siempre con forma además de color | Directo |
| Lectura del manuscrito | El papel es `--color-papel`, la tinta `--color-tinta` y la letra `--font-libro`. Sin logo dentro | Directo |
