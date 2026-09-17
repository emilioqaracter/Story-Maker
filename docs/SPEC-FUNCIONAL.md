# Story-Maker — Especificación funcional

**Versión 1.5** · 2026-09-17 · la parte técnica está en [SPEC-TECNICO.md](SPEC-TECNICO.md).

Este documento dice **qué hace el sistema y por qué**: quién trabaja, en qué
orden, quién aprueba y cómo se ve después lo que pasó.

---

## 1. Qué es esto

Un sistema de agentes que **escribe una novela corta** y deja ver, paso a paso,
cómo la escribió.

La novela es la excusa. Lo que se está construyendo es un **sistema agéntico
observable**: unos agentes escriben, otros aprueban o rechazan, y todo lo que
se decide queda anotado con su motivo.

La novela es un buen banco de pruebas porque los fallos se ven a simple vista.
Un personaje que reaparece después de haberse ido. Un final que llega en el
primer capítulo. Un capítulo bien escrito que no encaja con nada de lo
anterior.

> **El principio del que sale todo lo demás:** todo lo que se decide, lo decide
> un agente, y deja escrito por qué.

No hay reglas en código que aprueben o rechacen nada. Donde haría falta un
validador, hay un agente que lee y argumenta.

---

## 2. Los cinco agentes

| Agente | Qué hace | Qué decide |
|---|---|---|
| **arquitecto** | Convierte la idea y la longitud pedida en el plan de la novela: quién es el protagonista, qué quiere, qué se lo impide, y cómo se reparte la historia en introducción, nudo y desenlace. | el plan |
| **director** | Dice qué toca ahora y a quién le toca. Lleva la cuenta de por dónde va la novela y de cuándo un capítulo se ha atascado. | el turno |
| **redactor** | Escribe el capítulo. Cuando le llega una luz roja, lo reescribe atendiendo solo a lo que le señalaron. | nada |
| **revisor** | Lee el capítulo por sí solo. ¿Está bien escrito? Da luz verde o luz roja, siempre con el motivo. | si el capítulo está bien escrito |
| **verificador** | Lee el capítulo contra la historia hasta ahora y contra el plan. ¿Encaja? Da luz verde o luz roja, con el motivo. Cuando da verde, el capítulo entra en la novela. | si el capítulo entra |

**Por qué revisor y verificador son dos y no uno.** Juzgan cosas distintas y a
distinta escala. El revisor mira un capítulo aislado y le pregunta si está bien
escrito. El verificador mira la novela entera y le pregunta si este capítulo
pertenece. Un capítulo puede estar espléndidamente escrito y contradecir el
plan. Juntar las dos preguntas en un solo agente deja que una compense a la
otra, que es justo lo que no puede pasar.

**Y la sesión de Claude Code.** No está en la tabla porque no es un agente: es
**quien orquesta**. Lee la carpeta, despacha a los agentes, recoge sus luces y
va contando en voz alta lo que pasa. No hay ningún programa por debajo que la
conduzca: sigue una skill escrita, `dirigir-novela`, y usa las órdenes normales
de la terminal.

Al **director** lo consulta cuando no está claro cómo seguir. Para el camino
normal no hace falta, porque el ciclo se sigue solo.

Lo único que Claude Code no puede hacer nunca es **decidir que un capítulo está
bien**. Eso es del revisor y del verificador.

---

## 3. El flujo

### 3.1 De la idea al plan

```
  el usuario pide una novela
  «un ciclista que vuelve de una caída, unas 15.000 palabras»
        │
        ▼
  ┌──────────────┐
  │  ARQUITECTO  │   decide protagonista, meta, obstáculo y precio
  └──────────────┘   reparte la longitud en tres partes
        │            escribe un capítulo por línea
        ▼
     plan.md        ◄── el plan de la novela: un documento y nada más
```

### 3.2 El círculo de aprobación de un capítulo

Este es el corazón del sistema. Se repite una vez por capítulo.

```
  ┌───────────────────────── CAPÍTULO N ──────────────────────────┐
  │                                                                │
  │    ┌────────────┐                                              │
  │    │  REDACTOR  │ ──────────►  borrador del capítulo           │
  │    └────────────┘                      │                       │
  │          ▲                             ▼                       │
  │          │                    ┌─────────────────┐              │
  │          │    LUZ ROJA        │     REVISOR     │              │
  │          ├────────────────────┤  ¿está bien     │              │
  │          │    y el motivo     │   escrito?      │              │
  │          │                    └─────────────────┘              │
  │          │                             │ LUZ VERDE             │
  │          │                             ▼                       │
  │          │                    ┌─────────────────┐              │
  │          │    LUZ ROJA        │  VERIFICADOR    │              │
  │          └────────────────────┤  ¿encaja en la  │              │
  │               y el motivo     │   historia?     │              │
  │                               └─────────────────┘              │
  │                                        │ LUZ VERDE             │
  │                                        ▼                       │
  │                           el capítulo entra en la novela       │
  └────────────────────────────────────────────────────────────────┘
```

El revisor va primero porque es la pregunta más barata. No tiene sentido
comprobar si un capítulo encaja en la historia mientras todavía está mal
escrito.

Cada luz roja vuelve al redactor **con el motivo entero**, tal como lo escribió
quien juzgó, y el redactor toca solo lo que le señalaron.

Un capítulo corregido **vuelve a entrar por el principio**: pasa otra vez por el
revisor aunque la luz roja se la hubiera dado el verificador. Nadie hereda una
luz verde de un texto que ya no existe.

A los tres intentos sin las dos verdes, la sesión **para** el capítulo, le
enseña a la persona los motivos que se repiten y le pregunta si prefiere
cambiar el plan o bajar el listón.

### 3.3 Todo junto, hasta el final

```
  IDEA ──► ARQUITECTO ──► plan.md
                             │
                             ▼
                      ┌─────────────┐
            ┌────────►│  DIRECTOR   │  ¿qué toca ahora?
            │         └─────────────┘
            │                │
            │                ▼
            │      círculo de aprobación del capítulo N
            │         (redactor · revisor · verificador)
            │                │
            │                ▼
            │         capítulo aprobado
            │                │
            │                ▼
            │      ¿queda historia en el plan?
            │                │
            └───── sí ───────┤
                             │
                            no
                             ▼
                         novela.md
```

---

## 4. Luz verde y luz roja

Un capítulo solo avanza si **dos agentes le dan luz verde**. Cualquiera de los
dos puede darle **luz roja** y devolverlo al redactor.

Una luz roja sin motivo no sirve para nada, así que siempre trae tres cosas:

| | |
|---|---|
| **Qué está mal** | la frase que describe el problema |
| **Dónde** | una cita textual del capítulo, para no discutir de memoria |
| **Qué cambiar** | qué tendría que ocurrir para que la luz fuera verde |

Una luz verde también dice por qué. No hace falta que sea larga, pero tiene que
existir: es lo que permite leer una corrida entera después y entender qué
criterio se aplicó.

Todo esto se guarda. Una luz roja de hace tres intentos se puede releer.

---

## 5. El plan de la novela

El plan es **un documento**, `plan.md`, escrito en prosa por el arquitecto.
Nada se calcula y nada se deriva de otra cosa. Si algo hay que saberlo, está
escrito ahí con todas las letras.

Contiene:

- **Quién es el protagonista** y qué le importa.
- **Qué quiere**, qué se lo impide y qué le va a costar conseguirlo.
- **Las tres partes**: introducción, nudo y desenlace, con lo que pasa en cada
  una.
- **Los capítulos**, uno por línea, con lo que ocurre en cada uno.
- **La voz**: cómo suena este libro, en dos o tres frases.

El plan lo lee todo el mundo. El redactor escribe contra él, el verificador
comprueba contra él y el director se orienta con él.

**El plan solo lo cambia el arquitecto, y solo si se le pide.** Si un capítulo
contradice el plan, se cambia el capítulo. Es la única manera de que el plan
siga sirviendo de referencia cuando la novela va por la mitad.

---

## 6. La longitud

El usuario pide una longitud aproximada. No hace falta que sea exacta ni que la
tenga pensada de antemano. Vale «una novela corta» y vale «unas 20.000
palabras».

El **arquitecto** decide todo lo demás y lo deja escrito en el plan:

- Cuánto le toca a cada parte de la historia, en porcentaje y en palabras.
- Cuántos capítulos tiene cada parte.
- Cuántas palabras tiene que tener cada capítulo, aproximadamente.

Un reparto razonable de partida es una cuarta parte para la introducción, la
mitad para el nudo y una cuarta parte para el desenlace. Pero **lo decide el
arquitecto** según la historia que tenga entre manos, y lo justifica en el plan.

Nadie cuenta las palabras con un contador. El revisor sabe cuántas debería
tener el capítulo y avisa si se ha ido muy lejos.

---

## 7. La traza

Que se pueda ver después qué pasó y por qué es la mitad del proyecto. Pero
**esto no lo escribe ningún código propio**, por dos motivos.

### Las decisiones ya están en disco

Emitir un juicio **es** escribir un archivo. Cada luz, verde o roja, queda en
la carpeta de la novela con su veredicto, su motivo entero y su hora. No hay
un registro aparte que pudiera quedar incompleto, porque el registro es el
mismo acto de decidir.

Con solo esos archivos se responde: qué se decidió sobre un capítulo, por qué
se rechazó, cuántos intentos costó y qué acabó entrando en el libro.

### Langfuse lo recoge solo

Claude Code ya registra sus propias llamadas a agentes y herramientas. Langfuse
publica un plugin oficial que las captura y las manda, agrupadas por sesión,
sin que haya que escribir una línea.

Ahí se ve lo que los archivos no cuentan: cuánto tardó cada agente, cuánto
costó, y cómo se compara una corrida con la siguiente.

Es una capa aparte y se puede apagar. Sin ella el sistema funciona igual y las
decisiones siguen enteras en disco.

---

## 8. Las reglas que no se rompen

1. **Nadie aprueba su propio trabajo.** El redactor no decide si escribió bien.
   Los que deciden, revisor y verificador, no escriben prosa.
2. **Todo rechazo dice por qué**, con una cita y con qué cambiar. Un rechazo sin
   motivo no es accionable y no cuenta como rechazo.
3. **Los que juzgan no ven los intentos anteriores.** Cada revisión empieza con
   contexto limpio, para que el capítulo se juzgue por lo que es y no por lo que
   costó llegar hasta él.
4. **Decidir es escribir el archivo de la decisión.** No hay juicio que exista
   solo en una respuesta de chat.
5. **El plan solo lo cambia el arquitecto.** Si un capítulo lo contradice, se
   cambia el capítulo.
6. **El redactor toca solo lo que le señalaron.** Al corregir no reescribe lo
   que ya había pasado.
7. **La luz roja viaja entera.** Quien orquesta se la pasa al redactor tal como
   la escribió el juez, sin resumirla. Un resumen es una interpretación, y
   interpretar un juicio se parece demasiado a emitirlo.
8. **Una corrección se juzga otra vez desde cero**, por las dos luces, aunque
   solo una de las dos hubiera sido roja.

---

## 9. Las capas: qué se puede apagar

El sistema es **una pila de capas de control**, y cada una es un interruptor.
La de abajo escribe la novela. Cada una que se enciende encima añade un
control, y con él algo que antes no se veía.

Quitar una capa no rompe el sistema: lo deja escribiendo igual, con menos
control y menos visibilidad. Esa es la prueba de que cada capa se gana su
sitio, porque se puede apagar y ver exactamente qué se pierde.

| Capa | Qué aporta | Qué pasa si se apaga |
|---|---|---|
| **el plan** | arquitecto y redactor. Sin esto no hay novela. | no hay nada |
| **las decisiones en disco** | qué se decidió sobre cada capítulo y por qué | el sistema escribe igual, pero a ciegas |
| **el revisor** | la luz roja por cómo está escrito el capítulo | entra todo lo que el redactor produzca |
| **el verificador** | la luz roja por coherencia con la historia | los capítulos se contradicen entre sí |
| **el director** | el turno lo decide un agente | lo decide a mano la sesión de Claude Code |
| **Langfuse** | cuánto tardó y costó cada agente, y una corrida comparada con otra | las decisiones en disco siguen completas |

**Apagar una capa es no llamar a ese agente.** No hay una opción de
configuración en ningún sitio: si no se llama al verificador, esa capa está
apagada. Es deliberado, porque hace que el estado del sistema se vea en lo que
se ejecutó y no en un archivo de ajustes.

Las seis están construidas. El orden de la tabla sigue siendo el orden en que
conviene entenderlas, y la regla es que no se toca una capa sin poder explicar
la de abajo.

---

## 10. Historial

Toda modificación de esta especificación se registra aquí, en la misma entrega
que la cambia, con **qué** cambió y **por qué**.

| Versión | Fecha | Cambio | Por qué |
|---|---|---|---|
| **1.0** | 2026-09-17 | Primera versión. Cinco agentes: arquitecto, director, redactor, revisor y verificador. El círculo de aprobación por capítulo con dos luces. El plan como documento en prosa. La longitud repartida por el arquitecto en tres partes. La traza en disco, con Langfuse como capa aparte. | El sistema se construye desde cero con el criterio en manos de agentes y no de reglas en código, porque un criterio que se puede leer y discutir vale más que uno que solo se puede depurar. La unidad de trabajo es el capítulo. |
| **1.1** | 2026-09-17 | Las capas dejan de ser un orden de construcción y pasan a ser lo que se puede apagar, con una columna que dice qué se pierde al apagar cada una. | Se construyeron las seis de una vez, así que un orden de construcción ya no describe nada. Lo que sigue siendo cierto y útil es que cada capa es un interruptor, y que apagarla muestra exactamente qué control aportaba. |
| **1.2** | 2026-09-17 | La sesión de Claude Code orquesta siguiendo una skill, sin ningún programa por debajo. La traza deja de ser un archivo propio: las decisiones ya son archivos y Langfuse recoge los despachos con su plugin oficial. | El orquestador tenía que ser la sesión, y los scripts intermedios le estaban ocupando el sitio. Un registro aparte podía quedar incompleto; el archivo de una decisión no, porque escribirlo **es** decidir. |
| **1.3** | 2026-09-17 | La coherencia que juzga el verificador incluye los hechos que el capítulo afirma y las cuentas que echa. La luz roja viaja entera al redactor, y un capítulo corregido se vuelve a juzgar desde cero por las dos luces. Al tercer intento para la sesión. | La primera novela completa enseñó qué rechazos aparecen de verdad: un dato del mundo imposible para la edad del protagonista y una resta que no cerraba, ninguno de los dos una contradicción con el plan ni un problema de prosa. Y una corrección vuelve a pasar por el revisor, así que la regla tenía que decirlo en vez de dejarlo al criterio de quien orquesta. Parar es de la sesión, que es la que lleva la cuenta de los intentos. |
| **1.4** | 2026-09-17 | Sale de §2 el párrafo que ampliaba la coherencia del verificador a los hechos del mundo y a las cuentas del capítulo. Su competencia es la que describe su encargo: contradicciones con lo escrito y con el plan, el sitio en la historia, el tiempo y la repetición. | Lo que el verificador mira está escrito en su archivo, y ahí no dice nada de datos ni de aritmética: lo que cazó en la primera novela lo cazó por su regla de leer como un lector atento. Una spec que promete más de lo que el sistema encarga se vuelve una spec en la que no se puede confiar, y ampliar el encargo para sostener el párrafo era añadir una regla más a cambio de nada que hoy falte. |
| **1.5** | 2026-09-17 | Las dos especificaciones se mudan de la raíz del repositorio a `docs/`. El README las enlaza en su sitio nuevo. | La raíz es lo primero que se lee, y debe decir qué es esto y cómo se usa. Las specs son documentación de referencia: viven en la carpeta que se llama así, y quien llega al repositorio ve antes el sistema que su descripción. |
