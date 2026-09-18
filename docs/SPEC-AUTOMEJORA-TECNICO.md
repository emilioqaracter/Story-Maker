# Story-Maker — Automejora · Especificación técnica

**Versión 1.0** · 2026-09-18 · el qué y el porqué están en
[SPEC-AUTOMEJORA-FUNCIONAL.md](SPEC-AUTOMEJORA-FUNCIONAL.md). Cómo está hecho
el sistema que escribe la novela está en [SPEC-TECNICO.md](SPEC-TECNICO.md);
este documento no lo repite.

Este documento dice **cómo está hecho el loop**: archivos, órdenes, la
lección y qué puede tocar cada vuelta.

**Estado: construido, sin haber corrido.** La skill, las ideas, la bitácora
y la lección están en el árbol de trabajo. Ninguna novela ha corrido con
ellos. La tabla del §9 lo dice pieza por pieza.

---

## 1. Lo que añade al repositorio

```
.claude/skills/automejora/
  SKILL.md                     una vuelta del loop, orden por orden, para la sesión que afina
docs/automejora/
  ideas.md                     diez ideas, una por línea; la novela N usa la línea N
  bitacora.md                  una fila por novela
books/
  control-01/                  la novela 1, con la forma de cualquier novela
  control-02/                  la 2, y así hasta control-10/
```

Y una **rama de git**, `automejora`, donde el loop commitea. Un commit por
regla, otro por cada reversión, otro por cada fila de la bitácora. La rama
principal no se toca.

**Sigue sin haber código.** La sesión que afina sigue una skill y usa
`mkdir`, `sed`, `head`, `grep`, `ls` y `git`. Cada novela la escribe **otra
sesión de Claude Code**, lanzada con `claude -p`, que sigue `dirigir-novela`
sin ningún cambio. El loop lo lleva `/goal`, que es una orden de Claude Code
(§6). Langfuse no hace falta para nada de esto; si está, recibe la métrica
como puntuación (§7).

---

## 2. La lección, en los jueces y en la skill `luz`

Está en `revisor.md` y `verificador.md`, sección *La leccion*, y en
`.claude/skills/luz/SKILL.md`, en el formato y en las reglas.

**Formato.** La última línea de la luz, después del último bloque en una roja
o del motivo en una verde:

```
**Leccion:** <una frase>
```

**Reglas,** tal como las leen los jueces:

- La lección puede acabar copiada en las instrucciones del redactor como
  regla permanente. Si no serviría de regla para cualquier capítulo de
  cualquier novela, no es una lección.
- Nombra el hábito y lo dice como se escribe bien, no como se revisa. Lo que
  falló ya está arriba, con su cita.
- Sin citas, sin palabras del capítulo, sin nombres ni hechos de la novela.
  Si solo sirve para esta historia, no es una lección.
- Con las palabras más comunes que el juez encuentre, para que dos jueces que
  ven el mismo fallo escriban casi la misma frase y el loop pueda agruparlas.
- Una sola, la que más pesa, aunque la roja tenga cuatro bloques. Sin dos
  consejos encadenados con un «y».
- Nada de erratas, tildes, concordancia ni términos que cambian de grafía: eso
  lo limpia el redactor solo (§2.1). Si es el único problema, la luz va sin
  lección.
- Nombra la capacidad general, no la situación en que falló. La prueba: si la
  próxima escena no se pareciera en nada a esta, ¿la frase seguiría sirviendo?
- En una roja va siempre. En una verde va el `**Refuerzo:**` —la capacidad que
  el capítulo sostuvo— y además `**Leccion:**` si hay algo flojo.

El paso 5 de la skill cuenta solo las líneas `**Leccion:**`; los refuerzos
quedan fuera de la cuenta a propósito.

Cada juez lleva dos ejemplos buenos y tres malos de su propio terreno. Se lee
con una orden:

```bash
grep -h '^\*\*Leccion:\*\*' books/control-03/decisiones/*.md
```

---

### 2.1 Lo que el redactor se limpia solo

`redactor.md`, sección *Antes de entregar*. Antes de escribir el archivo del
borrador, el redactor relee lo que escribió y corrige ortografía y
acentuación, palabras cortadas o repetidas, concordancia, la grafía y el
género de cada nombre y término, la puntuación del diálogo, y la persona y el
tiempo verbal del plan dentro de los recuerdos y en la última frase.

Está ahí y no en un juez porque no hace falta criterio para verlo: un juez que
gasta una luz roja en una tilde le cuesta al redactor uno de sus tres
intentos, y una lección sobre erratas desplaza a la que enseña a escribir.

---

## 3. La puesta a punto

La hace la propia skill la primera vez que corre, si la rama no existe:

```bash
git checkout -b automejora
git add -A && git commit -m "Puesta a punto de la automejora"
```

El segundo paso **commitea todo lo que haya pendiente en el árbol de
trabajo**, porque el loop necesita partir de un estado commiteado para poder
revertir una regla sin arrastrar nada más. Si la persona prefiere commitear
a su manera, lo hace antes de lanzar el loop y la skill se encuentra el
árbol limpio.

`docs/automejora/ideas.md` trae diez ideas, una por línea, escritas de
antemano y variadas a propósito. La persona las cambia antes de empezar si
quiere; una vez lanzado el loop no se tocan. `docs/automejora/bitacora.md`
empieza con su cabecera y ninguna fila.

---

## 4. Una vuelta, orden por orden

Es lo que dice `.claude/skills/automejora/SKILL.md`. La sesión que afina la
sigue una vez por turno.

### 4.1 Dónde estoy

```bash
git branch --show-current                 # automejora; si no existe, la puesta a punto (§3)
grep -c '^| [0-9]' docs/automejora/bitacora.md    # cuántas novelas hay anotadas
tail -3 docs/automejora/bitacora.md
```

La próxima novela es la siguiente a la última fila. Si la última fila está
abierta, se retoma en el paso donde quedó, que la fila también dice.

### 4.2 Lanzar la novela

```bash
n=03; slug=control-$n
idea=$(sed -n "${n#0}p" docs/automejora/ideas.md)
mkdir -p books/$slug
claude -p "Sigue la skill dirigir-novela. Novela: books/$slug. Idea: $idea. Longitud: 1200 palabras en tres capitulos de unas 400 cada uno. No preguntes nada a nadie, no hay nadie delante: si un capitulo llega al tercer intento sin las dos verdes, deja la novela como esta y termina. Cuando los tres capitulos entren, cierra la novela con novela.md y termina." \
  --model sonnet --output-format json --dangerously-skip-permissions \
  > books/$slug/sesion.json
```

Se lanza **en segundo plano**, porque una novela tarda entre diez y quince
minutos. Se abre la fila de la bitácora con el número, la fecha, la idea y
"escribiendo", y se espera a que termine.

| Pieza | Por qué |
|---|---|
| una sesión aparte con `claude -p` | quien orquesta una novela acumula en su contexto el plan, las luces y los despachos. Diez novelas seguidas en la misma sesión son treinta capítulos de contexto, y eso no cabe bien. Cada novela empieza limpia |
| `dirigir-novela` sin cambios | el protocolo de la novela es el de siempre. Lo único que cambia entre novelas es el redactor |
| `--model sonnet` | quien orquesta corre en el mismo modelo en todas las novelas, para que no sea una variable más |
| `--output-format json` | la respuesta trae `session_id`, la sesión de Langfuse donde cae la traza de esa novela, y el coste |
| `--dangerously-skip-permissions` | la sesión corre sin nadie delante y no puede pedir permiso. Solo hace lo que dice `dirigir-novela` dentro de `books/`. Quien prefiera una lista cerrada la pone con `--allowedTools`; si alguna orden queda bloqueada, la novela termina sin capítulos y se ve en la bitácora |
| la longitud en el prompt | tres capítulos cortos: la novela sale en un cuarto de hora y la vuelta del loop también |

### 4.3 Contar

```bash
d=books/control-$n
for N in 01 02 03; do
  r=$(head -1 $d/decisiones/$N.intento1.revisor.md 2>/dev/null)
  v=$(head -1 $d/decisiones/$N.intento1.verificador.md 2>/dev/null)
  [ "$r" = "LUZ: VERDE" ] && [ "$v" = "LUZ: VERDE" ] && echo "$N entra"
done | wc -l                                          # Entran: 0 a 3
head -q -n1 $d/decisiones/*.revisor.md | grep -c ROJA          # rojas del revisor, todos los intentos
head -q -n1 $d/decisiones/*.verificador.md | grep -c ROJA      # rojas del verificador
ls $d/decisiones | sed 's/\.intento.*//' | sort | uniq -c       # intentos por capítulo
ls $d/novela.md                                                 # ¿terminó?
```

Un capítulo que no se escribió porque la novela paró antes cuenta como que
no entró.

### 4.4 Quedarse o revertir

| Situación | Qué se hace |
|---|---|
| novela 1 | no hay regla que juzgar: "sin regla" |
| Entran = 0 y la novela anterior dejó una regla | `git revert --no-edit <commit de esa regla>` y "se revierte" |
| todo lo demás | "se queda" |

Con tres muestras solo «cero de tres» es una señal. El commit de la regla es
el penúltimo de la rama, antes del de la bitácora; su hash está en la fila
anterior.

### 4.5 Contar las lecciones y hacer una regla

```bash
grep -h '^\*\*Leccion:\*\*' books/control-$n/decisiones/*.md
```

Como mucho una docena de líneas. La sesión las lee, agrupa las que dicen lo
mismo y toma el grupo más numeroso. Descarta cualquier lección que nombre un
personaje, un lugar o un hecho de la novela, y lo anota en la bitácora: es
una lección mal hecha y conviene saberlo, pero el loop no la usa. Si el grupo
más numeroso ya se probó y se revirtió, pasa al siguiente. Si no hay ninguna
lección, no hay regla esa vuelta, y la fila lo dice.

La regla es **una línea o dos en `redactor.md`**, en la sección *Como
escribir* si habla de escribir o en *Corregir* si habla de corregir, con la
forma de las que ya hay: una regla en negrita y una frase que la explica.
Dice lo que la lección dice, en general. Sin tocar el resto del archivo. Si
la lección más repetida ya está dicha en el archivo, la regla la reescribe
para que se entienda mejor en vez de repetirla.

```bash
git add .claude/agents/redactor.md
git commit -m "automejora $n · redactor: <la regla en una frase>

Novela $n: <Entran> de 3 a la primera.
Lecciones que la motivan:
- «<lección, textual>»  (cap 01, revisor)
- «<lección, textual>»  (cap 03, revisor)"
git rev-parse --short HEAD                            # va en la fila de la bitácora
```

Después se cierra la fila y se commitea aparte, para que el `revert` de la
regla sea limpio:

```bash
git add docs/automejora/bitacora.md && git commit -m "bitacora: novela $n"
```

### 4.6 Decir cómo va

La sesión termina el turno imprimiendo las tres últimas filas de la bitácora.
Es lo que `/goal` lee para saber si el loop terminó. Cuando el loop para,
por la meta o por las diez novelas, añade debajo de la tabla la
**comparación final**: capítulos a la primera en las novelas 1 a 3 y en las
tres últimas, nueve contra nueve, y se lo cuenta a la persona.

---

## 5. La bitácora

`docs/automejora/bitacora.md`. Una tabla, una fila por novela. Es el estado
del loop: `/goal` la lee, la sesión que afina la lee al empezar cada turno,
y la persona la lee al final.

```markdown
| Novela | Fecha | Idea | Regla que traía | Entran | Rojas rev. | Rojas ver. | Intentos | Terminó | Lección más repetida | Regla nueva | Decisión |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-09-19 | una farera en 1911… | ninguna | 1 | 3 | 1 | 5 | sí | erratas y palabras cortadas (3) | relee el capítulo entero antes de escribirlo · a1b2c3d | sin regla |
| 2 | 2026-09-19 | un repartidor en 2043… | relee el capítulo entero… | 2 | 1 | 2 | 4 | sí | cierres que explican (2) | termina en la última acción… · e4f5a6b | se queda |
| 3 | 2026-09-19 | una monja copista… | termina en la última acción… | 0 | 3 | 3 | 7 | no | resuelve cosas del plan antes de tiempo (4) | marca en el plan dónde termina tu capítulo… · c7d8e9f | se revierte |
```

| Columna | De dónde sale |
|---|---|
| Idea | la línea N de `ideas.md`, recortada |
| Regla que traía | la regla nueva de la fila anterior; "ninguna" en la 1 |
| Entran | capítulos con las dos primeras líneas del intento 1 en verde |
| Rojas rev. / ver. | primeras líneas `LUZ: ROJA` de cada juez, todos los intentos |
| Intentos | suma de intentos de los tres capítulos |
| Terminó | si existe `novela.md` |
| Lección más repetida | el grupo mayor y cuántas lecciones lo forman |
| Regla nueva | la frase del commit y su hash |
| Decisión | `sin regla`, `se queda`, `se revierte` |

Una fila **abierta** tiene la Decisión vacía y en Entran dice en qué paso
está: "escribiendo", "contando". Es lo que permite retomar.

---

## 6. Cómo corre el loop: `/goal`

`/goal` es una orden de Claude Code: fija una condición de fin, y la sesión
repite turnos hasta que la condición se cumple, hasta que juzga que es
imposible, o hasta `/goal clear`. Un modelo pequeño comprueba la condición
al final de cada turno leyendo lo que la sesión imprimió; por eso la skill
imprime la bitácora al terminar cada vuelta.

Se corre en una **sesión nueva**, en la raíz del repositorio, para que la
skill `automejora` esté cargada:

```
/goal En docs/automejora/bitacora.md, las dos últimas filas cerradas tienen Entran = 3 y Terminó = sí, o hay diez filas cerradas. Restricción: cada turno hace exactamente una novela siguiendo la skill automejora, y nada más.
```

y después:

```
Sigue la skill automejora.
```

Lo que hay que saber de `/goal` para este uso:

- **Espera a lo que corre en segundo plano.** La novela se lanza en segundo
  plano y `/goal` no evalúa la condición hasta que termina. A la media hora
  de espera la sesión recibe un aviso con lo que sigue corriendo; es normal
  si una novela se alarga.
- **Funciona sin nadie delante:** `claude -p "/goal …"` corre hasta
  cumplirla. Desde una sesión interactiva se ve mejor qué pasa, y es lo
  recomendable la primera vez.
- **Se corta con `Ctrl+C`** y se retoma con `--continue`: el objetivo se
  restaura solo, y la bitácora dice dónde se quedó.
- **Si varios turnos seguidos no usan herramientas, para solo.** Siguiendo
  la skill no pasa.
- Necesita que el proyecto sea de confianza para Claude Code, como los hooks.

---

## 7. Langfuse, si está

Cada novela es una sesión de Claude Code y el plugin la manda como traza
propia al cerrarse, con sus despachos nombrados. Además, la skill manda la
métrica de cada novela como puntuación numérica de **la sesión que afina**,
con la misma orden que `dirigir-novela` y el mismo `|| true`:

```bash
npx -y langfuse-cli --env .env api scores create --body-file - >/dev/null 2>&1 <<EOF || true
{
  "name": "entra-a-la-primera", "value": 2, "dataType": "NUMERIC",
  "sessionId": "$CLAUDE_CODE_SESSION_ID",
  "comment": "novela 03",
  "metadata": {"novela": 3, "entran": 2, "de": 3, "sesion_novela": "<session_id de sesion.json>"}
}
EOF
```

Con eso la curva del loop se ve en Langfuse sin abrir la bitácora, y desde
cada punto se llega a la traza de su novela. Si Langfuse no responde, el
loop sigue: la bitácora es la que manda.

---

## 8. Lo que el loop puede tocar y lo que no

| Archivo | Se puede tocar | Zona protegida |
|---|---|---|
| `.claude/agents/redactor.md` | *Como escribir*; dentro de *Los dos trabajos*, la parte *Corregir* | el frontmatter (`model`, `tools`); *Lo que recibis*, con lo que lee y en qué orden; *Que devolves*; la regla del bisturí |
| `docs/automejora/bitacora.md` | todo | |
| todo lo demás | **no** | revisor, verificador, skill `luz`, `dirigir-novela`, `automejora`, arquitecto, director, `ideas.md`, `settings.json`, las specs |

Lo protegido es el **diseño**: qué recibe el redactor, qué devuelve, en qué
modelo corre. Lo que se toca es el **criterio**: cómo escribe.

---

## 9. Qué hay construido y qué está comprobado

| Pieza | Construida | Comprobada corriendo |
|---|---|---|
| la lección en `revisor.md`, `verificador.md` y la skill `luz` | sí, en el árbol de trabajo | **no**: ningún juez ha corrido con ella |
| skill `automejora` | sí, en el árbol de trabajo | **no** |
| `docs/automejora/ideas.md`, diez ideas | sí | no aplica |
| `docs/automejora/bitacora.md`, vacía | sí | no aplica |
| lanzar una novela con `claude -p` desde otra sesión | sí, en la skill | **no**. Las novelas han corrido siempre con una persona delante |
| rama `automejora` y puesta a punto | en la skill | **no** |
| `/goal` como motor | en la skill | **no** |
| puntuación `entra-a-la-primera` en Langfuse | en la skill | **no** |

La novela 1 es la que comprueba todo junto, y es además la medida de
partida. Si la novela 1 termina sin capítulos, lo primero que se mira es
`books/control-01/sesion.json`: ahí está lo que la sesión anidada respondió.

**Lo que cuesta.** Una novela de tres capítulos cortos con quien orquesta en
Sonnet y el redactor en Haiku, con sus correcciones: entre 1 y 3 USD y entre
diez y quince minutos. Diez novelas, como mucho dos horas y media y unos
30 USD.

---

## 10. Historial técnico

| Versión | Fecha | Cambio | Por qué |
|---|---|---|---|
| **1.0** | 2026-09-18 | Primera versión. Skill `automejora` con una vuelta orden por orden. Diez ideas en `ideas.md`; cada novela en su sesión `claude -p` con `dirigir-novela` sin cambios, tres capítulos de unas cuatrocientas palabras. Métrica contada con `head -1` sobre el intento 1. Reversión solo ante cero de tres. Regla nueva en `redactor.md` a partir de la lección más repetida. Bitácora como estado del loop, `/goal` como motor, comparación final de tres novelas contra tres. Puesta a punto que crea la rama y commitea lo pendiente. Langfuse opcional. | La métrica es la aprobación del sistema y está en disco en cuanto los jueces escriben. Cada novela va en su sesión para que el contexto de quien orquesta no arrastre las anteriores, no por ninguna traza. Con tres muestras por vuelta solo «cero de tres» es señal, así que la reversión se reserva para eso y la comparación fina se hace al final con nueve contra nueve. El estado del loop es un archivo porque `/goal` decide leyendo lo que la sesión imprime. |
| **1.1** | 2026-09-18 | Sección 2 reescrita con las reglas nuevas de la lección y sección 2.1 con lo que el redactor se limpia solo antes de entregar. | Lo mismo que la 1.1 funcional, con el sitio exacto de cada regla: `redactor.md` sección *Antes de entregar*, `revisor.md` y `verificador.md` sección *La leccion*, y las dos reglas nuevas de la skill `luz`. |
| **1.2** | 2026-09-18 | Sección *La leccion* de los dos jueces reescrita con la escalera caso / situación / capacidad y su prueba, y con `**Refuerzo:**` obligatorio en toda luz verde. En la skill `luz`, el refuerzo entra en el formato, en el ejemplo de luz verde y en las reglas. El paso 5 de la skill `automejora` dice que los refuerzos no se cuentan. | Los jueces copian los ejemplos casi literalmente: una lección del control 4 era copia palabra por palabra del ejemplo «Bien» del revisor. Si el ejemplo está al nivel de la situación, todas las lecciones salen al nivel de la situación, así que el arreglo es el ejemplo y la escalera, no la advertencia. |
