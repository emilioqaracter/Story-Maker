---
name: automejora
description: Una vuelta del loop que ensena al redactor a escribir capitulos que entren a la primera - lanza una novela de control en su propia sesion, cuenta cuantos capitulos entraron a la primera, convierte la leccion mas repetida de los jueces en una regla del redactor y lo anota en la bitacora. Usala cuando pidan correr, seguir o retomar la automejora.
---

# Una vuelta de la automejora

Vos sos la sesion que afina. En cada turno haces **exactamente una vuelta**:
una novela, una cuenta, una regla. Ni dos novelas, ni dos reglas.

No juzgas capitulos. No escribis prosa. No decidis que habito falla: eso lo
dicen los jueces en su leccion, y vos contas. La spec esta en
`docs/SPEC-AUTOMEJORA-FUNCIONAL.md` y `docs/SPEC-AUTOMEJORA-TECNICO.md`; no
hace falta leerlas para seguir esto.

## 0. Donde estoy

```bash
git branch --show-current
tail -3 docs/automejora/bitacora.md
```

- Si la rama **no** es `automejora`, hace la puesta a punto del paso 1.
- La proxima novela es la siguiente a la ultima fila de la bitacora. Si no
  hay filas, es la 1.
- Si la ultima fila esta **abierta** (sin Decision), retomala en el paso que
  dice su columna Entran: "escribiendo" -> paso 3, "contando" -> paso 4.
- Si ya hay diez filas cerradas, o las dos ultimas cerradas tienen Entran = 3
  y Termino = si, el loop termino: anda al paso 8.

## 1. Puesta a punto (solo la primera vez)

```bash
git checkout -b automejora
git add -A && git commit -m "Puesta a punto de la automejora"
```

Esto commitea todo lo pendiente del arbol de trabajo. Hace falta para que
despues una regla se pueda revertir sola, sin arrastrar nada mas. Si el
arbol ya esta limpio, el commit no hace nada y sigue.

## 2. Lanzar la novela

`n` es el numero de la novela con dos digitos (`01`, `02`, ... `10`). La
idea es la linea `n` de `docs/automejora/ideas.md`.

Primero abri la fila en la bitacora: numero, fecha, idea recortada, la regla
que traia (la "Regla nueva" de la fila anterior, o "ninguna"), y en Entran
la palabra `escribiendo`. Las demas columnas vacias.

Despues, **en segundo plano** con la herramienta Bash:

```bash
n=03; slug=control-$n
idea=$(sed -n "${n#0}p" docs/automejora/ideas.md)
mkdir -p books/$slug
claude -p "Sigue la skill dirigir-novela. Novela: books/$slug. Idea: $idea. Longitud: 1200 palabras en tres capitulos de unas 400 cada uno. No preguntes nada a nadie, no hay nadie delante: si un capitulo llega al tercer intento sin las dos verdes, deja la novela como esta y termina. Cuando los tres capitulos entren, cierra la novela con novela.md y termina." \
  --model sonnet --output-format json --dangerously-skip-permissions \
  > books/$slug/sesion.json
```

Tarda entre diez y quince minutos. **Espera el aviso de que termino.** No
mires la carpeta a medias ni la interpretes: la novela la dirige la otra
sesion, y vos no intervenis.

## 3. Contar

```bash
n=03; d=books/control-$n
for N in 01 02 03; do
  r=$(head -1 $d/decisiones/$N.intento1.revisor.md 2>/dev/null)
  v=$(head -1 $d/decisiones/$N.intento1.verificador.md 2>/dev/null)
  [ "$r" = "LUZ: VERDE" ] && [ "$v" = "LUZ: VERDE" ] && echo "$N entra"
done | wc -l
head -q -n1 $d/decisiones/*.revisor.md | grep -c ROJA
head -q -n1 $d/decisiones/*.verificador.md | grep -c ROJA
ls $d/decisiones | sed 's/\.intento.*//' | sort | uniq -c
ls $d/novela.md
```

Eso da, en orden: **Entran** (0 a 3), rojas del revisor, rojas del
verificador, intentos por capitulo (sumalos), y si **Termino** (existe
`novela.md`). Un capitulo que no se escribio cuenta como que no entro.

Anota todo en la fila y pone en Entran el numero. Si Langfuse esta, manda la
metrica; si falla, seguis:

```bash
sid=$(grep -o '"session_id":"[^"]*"' books/control-$n/sesion.json | head -1 | cut -d'"' -f4)
npx -y langfuse-cli --env .env api scores create --body-file - >/dev/null 2>&1 <<EOF || true
{
  "name": "entra-a-la-primera", "value": <Entran>, "dataType": "NUMERIC",
  "sessionId": "$CLAUDE_CODE_SESSION_ID",
  "comment": "novela $n",
  "metadata": {"novela": ${n#0}, "entran": <Entran>, "de": 3, "sesion_novela": "$sid"}
}
EOF
```

## 4. Quedarse o revertir

| Situacion | Decision |
|---|---|
| es la novela 1 | `sin regla` |
| Entran = 0 **y** la fila anterior dejo una regla nueva | `git revert --no-edit <hash de esa regla>` y `se revierte` |
| todo lo demas | `se queda` |

El hash esta en la columna "Regla nueva" de la fila anterior. Con tres
muestras solo "cero de tres" es una senal; no revertis por menos.

## 5. Contar las lecciones

```bash
grep -h '^\*\*Leccion:\*\*' books/control-$n/decisiones/*.md
```

Leelas todas. Agrupa las que dicen lo mismo y toma el grupo mas numeroso.
Anota en la fila "Leccion mas repetida" con cuantas la forman.

- **Descarta** cualquier leccion que nombre un personaje, un lugar, una
  palabra del capitulo o un hecho de la novela. Anotalo en la fila, entre
  parentesis: "(1 descartada por nombrar la historia)". No la uses.
- Si el grupo mas numeroso ya se probo como regla y se revirtio (miralo en
  la bitacora), pasa al siguiente grupo.
- Si no queda ninguna leccion, esta vuelta no hay regla: la fila dice
  "ninguna" en Regla nueva y saltas al paso 7.

## 6. Hacer la regla y commitearla

Abri `.claude/agents/redactor.md`. Solo podes tocar dos sitios:

- la seccion **Como escribir**, si la leccion habla de escribir;
- la parte **Corregir** de *Los dos trabajos*, si habla de corregir.

La regla es **una o dos lineas** con la forma de las que ya hay: una frase en
negrita y una frase que la explica. Dice lo que la leccion dice, en general.
Si el archivo ya dice algo parecido, reescribi esa linea para que se
entienda mejor en vez de anadir otra. **Nunca** toques el frontmatter, *Lo
que recibis*, *Que devolves* ni la regla del bisturi. Nunca menciones una
novela.

```bash
git add .claude/agents/redactor.md
git commit -m "automejora $n · redactor: <la regla en una frase>

Novela $n: <Entran> de 3 a la primera.
Lecciones que la motivan:
- «<leccion textual>»  (cap 01, revisor)
- «<leccion textual>»  (cap 03, revisor)"
git rev-parse --short HEAD
```

Anota en "Regla nueva" la frase y el hash.

## 7. Cerrar la fila

Pone la Decision del paso 4, guarda la bitacora y commiteala aparte:

```bash
git add docs/automejora/bitacora.md && git commit -m "bitacora: novela $n"
tail -3 docs/automejora/bitacora.md
```

**Termina el turno imprimiendo esas tres filas.** Es lo que `/goal` lee.

## 8. Cuando el loop termina

Si las dos ultimas filas cerradas tienen Entran = 3 y Termino = si, o si hay
diez filas cerradas, no lances mas novelas. Debajo de la tabla de la
bitacora escribi la **comparacion final**: capitulos a la primera en las
novelas 1 a 3 y en las tres ultimas, nueve contra nueve, y una linea con lo
que eso dice. Commitea la bitacora y contaselo a la persona: cuantas
novelas, que reglas quedaron, cuales se revirtieron, y la comparacion.

## Lo que nunca haces

- **No juzgas un capitulo ni corriges una luz.** La metrica es lo que dicen
  los archivos de `decisiones/`.
- **No tocas a los jueces, ni la skill `luz`, ni `dirigir-novela`, ni el
  arquitecto, ni `ideas.md`.** Solo `redactor.md` y la bitacora.
- **No haces dos reglas en una vuelta.** Ni una regla que hable de una
  novela.
- **No intervenis en la novela mientras corre.** Si termina sin capitulos,
  lo anotas, miras `sesion.json` para contarselo a la persona, y seguis con
  la siguiente idea. Cada idea se usa una vez.
- **No paras porque Langfuse no responda.**
