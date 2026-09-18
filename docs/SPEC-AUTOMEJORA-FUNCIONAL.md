# Story-Maker — Automejora · Especificación funcional

**Versión 1.0** · 2026-09-18 · la parte técnica está en
[SPEC-AUTOMEJORA-TECNICO.md](SPEC-AUTOMEJORA-TECNICO.md). El sistema que
escribe la novela está descrito en [SPEC-FUNCIONAL.md](SPEC-FUNCIONAL.md);
este documento no lo repite.

Este documento dice **qué hace el loop de automejora y por qué**: qué mide,
qué mueve, cómo aprende y cuándo para.

---

## 1. Qué es esto

Un loop que **enseña al redactor a escribir capítulos que entren a la
primera**. Escribe una novela corta de tres capítulos, como siempre, con
arquitecto, redactor y los dos jueces. Cuenta cuántos de los tres capítulos
recibieron las dos luces verdes en su primer intento. Lee la lección que los
jueces le dejaron al redactor, convierte la más repetida en una regla del
redactor, y escribe la novela siguiente, que es **otra novela**, con otra
idea. Así hasta diez.

Casi ningún capítulo entra hoy a la primera. En `adrian-2025` ninguno de
cinco; en `veterano-2010` y `ciclista-2010`, uno de tres. Y las luces rojas
del primer intento repiten los mismos fallos del redactor: erratas y palabras
cortadas, frases que no se entienden, cierres que explican en vez de mostrar,
capítulos que se pasan de largo, imágenes que repiten las del capítulo
anterior, cosas del plan resueltas antes de tiempo.

> **El principio del que sale todo lo demás:** lo que se mueve es el
> redactor; lo que no se mueve son los jueces, que son la vara.

Si el loop pudiera tocar a los jueces, podría cumplir la meta ablandando el
criterio. Con los jueces fijos, la métrica solo sube si el redactor escribe
capítulos que los jueces de hoy aprueban.

---

## 2. La métrica

**Capítulos que entran a la primera:** de los tres capítulos de una novela,
cuántos recibieron luz verde del revisor **y** del verificador en su primer
intento. Vale 0, 1, 2 o 3.

Se cuenta con las primeras líneas de los archivos de `decisiones/`. No hace
falta ningún evaluador ni ningún modelo que puntúe: la métrica es la propia
aprobación del sistema, la misma que decide si un capítulo entra en el libro.

Lo que **no** mide: si el capítulo es buena literatura. Mide si satisface a
los jueces del sistema, que es la definición de éxito que el sistema ya
tiene. Si los jueces se equivocan, el redactor aprenderá a satisfacer un
error; afinar a los jueces es otro loop, con otra vara.

---

## 3. Lo fijo y lo que se mueve

| Fijo durante todo el loop | Se mueve, una regla por novela |
|---|---|
| el revisor y el verificador, con su skill `luz` | el agente **redactor**: cómo escribe |
| el arquitecto, el director y la skill `dirigir-novela` | |
| la lista de diez ideas y la longitud de cada novela | |
| el modelo de cada agente y el de quien orquesta | |
| la meta y las condiciones de parada | |

Solo se mueve el redactor porque la métrica mide su trabajo. Los jueces son
la vara. El arquitecto y `dirigir-novela` son el protocolo: si cambiaran
entre novelas, dos novelas dejarían de ser comparables.

De lo que el redactor puede cambiar, solo su **criterio**: cómo escribe y
cómo corrige. Lo que recibe, lo que lee, lo que devuelve y en qué modelo
corre son diseño, y no se tocan.

---

## 4. Por qué diez novelas distintas y no una

Porque un loop que itera sobre la misma novela puede aprenderse la novela. Al
cabo de unas vueltas, las reglas del redactor hablarían de esa historia y de
sus trampas, la métrica subiría, y el redactor no habría aprendido a escribir
sino a escribir eso. Con una novela distinta cada vez no hay historia que
repetir: cada regla se mide sobre una novela que nadie había visto, y la
prueba de que la regla sirve para cualquier novela viene incluida.

Las diez ideas están escritas de antemano, una por línea, en un archivo del
repositorio, y son variadas a propósito: distintos géneros, épocas, voces y
protagonistas. Si las diez se parecieran, el redactor podría aprenderse un
género en vez de una historia, que es la misma trampa un escalón más arriba.

**Lo que se paga.** Cada novela trae su dificultad: un plan con más saltos
de tiempo da más trabajo al verificador aunque el redactor no haya cambiado.
Y tres capítulos son tres muestras: la métrica salta de a uno. Con ese ruido
no se puede decir, novela a novela, si una regla mejoró o empeoró un poco
las cosas. Eso cambia cómo se decide (§6) y cuándo se para (§7): las
decisiones se toman con lo que tres muestras sí pueden decir, y la
comparación fina se hace al final, con treinta.

Cada novela tiene tres capítulos cortos, de unas cuatrocientas palabras,
para que una vuelta del loop no tarde más de un cuarto de hora.

---

## 5. Cómo aprende: la lección

Cada luz termina con **una lección**: una frase que el juez le deja al
redactor sobre el hábito que falla, no sobre el caso. En una roja va siempre;
en una verde, solo si hay algo flojo que se repite.

| Lo que ya dice la luz | Lo que dice la lección |
|---|---|
| «Escribiste "desmorono" sin tilde y "el el" repetido», con la cita | «Estás entregando erratas y palabras cortadas: relee el capítulo entero antes de escribirlo.» |
| «El festejo repite la coreografía del capítulo anterior», con la cita | «Estás repitiendo la imagen de cierre del capítulo anterior: léelo antes de escribir el tuyo y busca otra.» |

**Por qué la lección la escribe el juez y no el loop.** El juez es quien vio
el fallo y puede decir de qué tipo es. Si el loop tuviera que deducir el
hábito a partir de una lista de citas, estaría juzgando, y eso no le toca.
Con la lección, al loop le queda contar: qué lección se repite más.

**Por qué la lección no lleva citas, ni nombres, ni hechos de la novela.**
Con diez novelas distintas el redactor no puede aprenderse una historia,
pero una regla que hablara de un personaje concreto seguiría siendo inútil
para la novela siguiente. La lección lo tiene prohibido por escrito, y el
loop descarta cualquiera que lo haga.

La lección es parte del formato de la luz, y la leen también los redactores
de las novelas normales cuando corrigen. No es solo para el loop.

---

## 6. El ciclo

```
  ┌────────────────────── novela N ─────────────────────────┐
  │                                                         │
  │   1. escribir la novela N con la idea N, en una         │
  │        sesión propia, con dirigir-novela tal como es    │
  │                     │                                   │
  │                     ▼                                   │
  │   2. contar: ¿cuántos de los tres capítulos             │
  │        entraron a la primera?                           │
  │        cero, después de una regla nueva: se revierte    │
  │        lo demás: la regla se queda                      │
  │                     │                                   │
  │                     ▼                                   │
  │   3. leer las lecciones de las luces, tomar la que      │
  │        más se repite, y hacer UNA regla en el redactor  │
  │        anotada y commiteada                             │
  └─────────────────────────────────────────────────────────┘
        │
        ▼
   ¿meta cumplida? sí → parar.   ¿diez novelas? sí → parar.   no → N+1
```

**La novela 1 se escribe sin regla.** Es la medida de partida.

**La novela se escribe entera, con sus correcciones.** El capítulo 2 necesita
el 1 aprobado, así que si el 1 no entra a la primera se corrige y se sigue,
como en cualquier novela. La métrica solo mira el primer intento de cada
capítulo; el ciclo de corrección está para poder llegar al capítulo
siguiente.

**Una regla por novela.** Añadida, quitada o reescrita en una sola sección
del redactor. Si se cambian dos y la métrica sube, no se sabe cuál lo hizo;
si baja, no se sabe cuál revertir.

**La regla sale de la lección que más se repite.** El loop no inventa:
cuenta lecciones y escribe la más frecuente como regla, con las lecciones
citadas en el commit. Si esa ya se probó y se revirtió, la siguiente.

**Solo se revierte ante un desastre claro.** Con tres muestras no se puede
distinguir «mejor» de «igual» ni de «un poco peor»: una novela difícil baja
la métrica sin que el redactor tenga culpa. Lo que tres muestras sí pueden
decir es «cero de tres»: si la novela que siguió a una regla nueva no metió
ni un capítulo a la primera, la regla se revierte. Todo lo demás se queda.
La comparación fina se hace al final (§7).

---

## 7. La meta y cuándo para

**La meta: dos novelas seguidas con sus tres capítulos a la primera.** Seis
de seis.

El loop para cuando ocurre lo primero de esto:

| Condición | Por qué |
|---|---|
| **Dos novelas seguidas** con tres de tres | Una sola novela entera a la primera sale por suerte: si el redactor acierta la mitad de las veces, tres de tres le sale una de cada ocho novelas, y en diez intentos casi seguro que le sale alguna. Dos seguidas le salen una de cada sesenta. Con dos seguidas, cumplir la meta dice que el redactor anda cerca del 80 % o más. |
| **Diez novelas** sin cumplirla | Se agotaron las ideas. Diez reglas son muchas para un archivo de agente; si con eso no se llegó, lo tiene que mirar una persona. |

Al parar, el loop deja en la bitácora una **comparación final**: cuántos
capítulos entraron a la primera en las tres primeras novelas y cuántos en las
tres últimas. Nueve muestras contra nueve. Es la única comparación del loop
con muestras suficientes, y es la que dice si el redactor aprendió algo,
haya cumplido la meta o no.

**Por qué no el 100 % en una sola novela.** Un redactor que corre en el
modelo barato deja una errata cada tanto, y un juez que corre en un modelo
duda cada tanto. Tres de tres una vez es un resultado que la suerte da y
quita, y el loop pararía en una novela afortunada sin haber aprendido.

---

## 8. Quién decide qué

| Decisión | Quién | Cómo queda escrita |
|---|---|---|
| si un capítulo entra a la primera | **el revisor y el verificador**, como siempre | sus luces, en `decisiones/` |
| qué hábito falla | **el juez**, en la lección | la última línea de la luz |
| qué regla cambiar | **la sesión que afina**, contando lecciones y siguiendo la skill `automejora` | la fila de la bitácora y el commit, con las lecciones citadas |
| si una regla se revierte | **la medida**: cero de tres tras una regla nueva | la reversión |
| las diez ideas y la longitud | **la persona**, una vez, antes de empezar | `docs/automejora/ideas.md` |
| llevar los cambios a la rama principal | **la persona**, al terminar | el merge |

La sesión que afina **no juzga capítulos, no escribe prosa y no decide qué
hábito falla**. Lanza la novela, cuenta, escribe la lección más repetida
como regla, anota y commitea. Los cambios se aceptan solos dentro de la rama
del loop.

---

## 9. Las reglas que no se rompen

1. **Los jueces no se tocan** mientras el loop corre. Ni su archivo, ni la
   skill `luz`, ni su modelo.
2. **Una regla por novela**, en el redactor, en una sola sección.
3. **Lo que el redactor recibe, lee y devuelve no se cambia.** Se cambia
   cómo escribe.
4. **Las reglas son generales.** Ninguna menciona un personaje, un hecho,
   una palabra ni nada de ninguna novela. Una lección que lo haga se
   descarta, y se anota.
5. **Toda regla cita sus lecciones**, textuales, en el commit.
6. **Lo revertido no se vuelve a probar.**
7. **Nadie corrige una luz ni cuenta un capítulo a mano.** La métrica es lo
   que dicen los archivos de `decisiones/`.
8. **Cada idea se usa una vez.** Una novela que no terminó cuenta igual, con
   lo que alcanzó a escribir; no se repite con la misma idea.
9. **Nada llega a la rama principal solo.**

---

## 10. La capa

Es una capa más encima de la de Langfuse, en la pila que describe la
especificación del sistema principal:

| Capa | Qué aporta | Qué pasa si se apaga |
|---|---|---|
| **la automejora** | el redactor aprende de las lecciones de los jueces sin que nadie lo retoque, y queda escrito qué regla se añadió y por qué | el sistema escribe igual; al redactor lo afina una persona leyendo luces, o nadie |

Apagarla es no correr la skill `automejora`. La lección, en cambio, se queda:
es parte de la luz y les sirve a los redactores de las novelas normales.

---

## 11. Historial

Toda modificación de esta especificación se registra aquí, en la misma
entrega que la cambia, con **qué** cambió y **por qué**.

| Versión | Fecha | Cambio | Por qué |
|---|---|---|---|
| **1.0** | 2026-09-18 | Primera versión. Un loop que escribe hasta diez novelas distintas de tres capítulos cortos, cada una en su sesión, con el sistema tal como es; cuenta cuántos capítulos entraron a la primera; convierte la lección más repetida de los jueces en una regla del redactor por novela; revierte solo ante cero de tres. Jueces fijos. Meta: dos novelas seguidas con tres de tres, o diez novelas, con una comparación final de las tres primeras contra las tres últimas. Cada luz termina con una lección general para el redactor. | Casi ningún capítulo entra a la primera y las rojas del primer intento repiten los mismos fallos del redactor. La aprobación del sistema ya es una métrica que se cuenta con la terminal. Se eligen novelas distintas para que el redactor no pueda aprenderse una historia, y por eso mismo la métrica queda con tres muestras por vuelta: las decisiones se ajustan a lo que tres muestras pueden decir y la comparación fina se hace al final. La meta se pide dos veces porque una novela entera a la primera sale por suerte. La lección la escribe el juez porque es quien vio el fallo. Va en su propia especificación para que el sistema que escribe la novela siga describiéndose solo. |
