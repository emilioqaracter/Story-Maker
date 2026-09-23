# definitions.md

> Documentación de dominio · ver [`../AGENTS.md`](../AGENTS.md) para el índice completo.
> Relacionados: [domain-knowledge](domain-knowledge.md) · [architecture](architecture.md) · [verification](verification.md)

Ontología de dominio para un sistema de IA generador de novelas largas (caso de referencia: épica deportiva).

Este documento define **qué existe** en el dominio. No describe cómo se implementa (ver `architecture.md`) ni cómo se relacionan visualmente las entidades (ver `domain-knowledge.md`).

---

## 0. Cómo usar este documento

**Convenciones**

- Cada término tiene un identificador estable `PREFIJO-NN`. Los otros documentos referencian por ID, no por nombre, para que renombrar no rompa trazabilidad.
- **Entidad**: algo que tiene identidad propia y persiste. Se guarda en el canon.
- **Atributo**: propiedad de una entidad. No tiene identidad propia.
- **Relación**: vínculo entre entidades. Puede tener atributos propios y vigencia temporal.
- **Invariante**: regla que debe cumplirse siempre. Su violación es un defecto.

**Espacios de nombres**

| Prefijo | Capa | Pregunta que responde |
|---|---|---|
| `MET` | Metamodelo | ¿Con qué piezas se construye la ontología? |
| `EST` | Estructura narrativa | ¿Cómo se divide el texto? |
| `PER` | Agentes narrativos | ¿Quién actúa? |
| `MUN` | Mundo | ¿Dónde y bajo qué reglas? |
| `DEP` | Subdominio deportivo | ¿Qué es específico de la épica deportiva? |
| `POE` | Poética y estilo | ¿Cómo suena y qué significa? |
| `CAN` | Canon y continuidad | ¿Qué es verdad y sigue siendo verdad? |
| `CTX` | Contexto | ¿Qué sabe el modelo en cada llamada? |
| `CAL` | Calidad | ¿Cómo sabemos que está bien? |
| `PRO` | Proceso | ¿Cómo se produce? |

**Regla de oro del dominio**: una novela larga no es un texto largo. Es un **estado del mundo que evoluciona** y del cual el texto es solo la proyección visible. El sistema debe gestionar el estado, no solo la prosa.

**Dos restricciones que atraviesan toda la ontología**

- **Autonomía completa (PRO-11)**: no hay validación externa en ningún punto del ciclo. Cada decisión que en otro diseño resolvería una persona necesita aquí una regla de precedencia, un umbral numérico o un agente con responsabilidad asignada. Donde no exista ninguna de las tres cosas, hay un agujero de diseño.
- **100.000 tokens de entrada, en dos techos distintos**: el de una llamada (CTX-01) y el de concurrencia del sistema (CTX-20), que acota la suma de todo lo que está en vuelo en el mismo instante. Los fija el proyecto, no el proveedor. Lo que no quepa se resuelve con jerarquía de resúmenes, recuperación selectiva y aislamiento de subtareas, nunca con truncamiento.

---

## 1. MET — Metamodelo

| ID | Término | Definición |
|---|---|---|
| MET-01 | **Entidad** | Objeto del dominio con identidad persistente y ciclo de vida propio. Se puede referenciar desde cualquier punto de la obra. |
| MET-02 | **Atributo** | Propiedad de una entidad, con tipo y, si aplica, vigencia temporal. |
| MET-03 | **Relación** | Vínculo tipado entre dos entidades, direccional o no, con vigencia temporal. |
| MET-04 | **Invariante** | Restricción que toda instancia del modelo debe satisfacer. Se verifica de forma automática siempre que sea posible. |
| MET-05 | **Evento** | Hecho que ocurre en un instante de la línea temporal del mundo y que modifica el estado de una o más entidades. Unidad atómica del canon. |
| MET-06 | **Estado en t** | Proyección del conjunto de eventos ocurridos hasta el instante `t`. Es derivado, nunca se edita a mano. |
| MET-07 | **Vigencia** | Par `desde / hasta` en tiempo de mundo que acota cuándo un atributo o relación es cierto. Sin vigencia no hay continuidad verificable. |
| MET-08 | **Faceta** | Vista parcial de una entidad, adaptada a un consumidor concreto (por ejemplo, la ficha de 80 palabras de un personaje frente a su ficha completa). |
| MET-09 | **Procedencia** | Origen de un dato: venía fijado en el brief, lo generó el modelo, se extrajo de la prosa o se derivó por cálculo. Condiciona su precedencia al resolver conflictos. |

---

## 2. EST — Estructura narrativa

| ID | Término | Definición | Notas de granularidad |
|---|---|---|---|
| EST-01 | **Universo** | Contenedor máximo. Conjunto de reglas, lugares y entidades compartidos por una o varias obras. | |
| EST-02 | **Saga** | Secuencia ordenada de obras que comparten universo y continuidad. | |
| EST-03 | **Obra** | La novela. Unidad de publicación y de intención autoral. | 80.000–200.000 palabras típicas |
| EST-04 | **Parte / Libro** | División mayor opcional, normalmente ligada a un salto temporal o de escenario. | |
| EST-05 | **Acto** | División funcional según la progresión dramática, no según el índice. Una obra suele tener 3 o 5. | |
| EST-06 | **Arco** | Trayectoria de transformación con inicio, crisis y resolución. Puede ser de trama, de personaje o temático. Atraviesa capítulos y no coincide necesariamente con ellos. | |
| EST-07 | **Capítulo** | Unidad de lectura y de publicación interna. Es la unidad natural de generación y de control de calidad. | 1.500–4.000 palabras |
| EST-08 | **Escena** | Unidad dramática continua en tiempo, espacio y punto de vista. Cambia una de las tres cosas y empieza otra escena. | 400–1.500 palabras |
| EST-09 | **Secuencia** | Cadena de escenas unidas por una misma tensión inmediata (por ejemplo, un partido completo contado en cuatro escenas). | |
| EST-10 | **Beat** | Micro-unidad de cambio dentro de una escena: una acción, una reacción, un giro de valor. | 1–3 párrafos |
| EST-11 | **Línea argumental** | Hilo de causalidad que puede seguirse de principio a fin de forma independiente. Una novela sostiene entre 3 y 7 antes de volverse ilegible. | |
| EST-12 | **Escaleta / Outline** | Plan ordenado de escenas con su función, personajes, cambio de valor y consecuencias en el estado. Es el contrato entre planificación y redacción. | |
| EST-13 | **Cambio de valor** | Diferencia de carga emocional o de situación entre el inicio y el final de una escena. Una escena sin cambio de valor es relleno. | |
| EST-14 | **Función de escena** | Rol de la escena en el arco: establecer, complicar, revelar, decidir, culminar, asimilar. | |
| EST-15 | **Transición** | Mecanismo de paso entre escenas: corte, elipsis, sumario, salto de POV. Determina el ritmo percibido. | |
| EST-16 | **Elipsis** | Tiempo de mundo que transcurre sin narrarse. Debe registrarse igualmente en el estado, porque el mundo sigue avanzando. |

**Invariante EST-I1**: toda escena pertenece a exactamente un capítulo, tiene exactamente un POV y al menos un cambio de valor declarado.
**Invariante EST-I2**: todo arco abierto debe cerrarse o declararse explícitamente como abierto hacia la siguiente obra.

---

## 3. PER — Agentes narrativos

| ID | Término | Definición |
|---|---|---|
| PER-01 | **Personaje** | Entidad con agencia, deseo y capacidad de cambiar. Núcleo del canon junto con los eventos. |
| PER-02 | **Rol actancial** | Función estructural que ocupa un personaje respecto al protagonista en un arco dado: sujeto, objeto, oponente, ayudante, destinador, destinatario. Es relativo al arco, no fijo. |
| PER-03 | **Deseo (want)** | Objetivo consciente y declarable del personaje. Mueve la trama. |
| PER-04 | **Necesidad (need)** | Carencia interna que el personaje no reconoce. Mueve el arco. La tensión entre PER-03 y PER-04 es el motor emocional. |
| PER-05 | **Herida** | Suceso del pasado que explica la creencia limitante del personaje. |
| PER-06 | **Arco de personaje** | Secuencia de estados internos: creencia inicial, grietas, crisis, decisión, nueva creencia. Puede ser positivo, plano o de caída. |
| PER-07 | **Voz** | Firma lingüística del personaje: léxico, longitud de frase, muletillas, temas recurrentes, qué calla. Debe ser distinguible sin etiqueta de diálogo. |
| PER-08 | **Idiolecto** | Conjunto cerrado de marcadores léxicos y sintácticos que definen operativamente la voz. Es la forma verificable de PER-07. |
| PER-09 | **Competencia** | Lo que el personaje sabe y puede hacer en el instante `t`. Límite duro de verosimilitud: nadie ejecuta algo que no ha aprendido en escena. |
| PER-10 | **Conocimiento (who-knows-what)** | Conjunto de hechos canónicos que un personaje conoce en `t`. Gestionarlo mal es la causa número uno de incoherencias en novelas generadas. |
| PER-11 | **Relación interpersonal** | Vínculo tipado entre dos personajes con valencia, intensidad y vigencia. Evoluciona por eventos, no por decreto. |
| PER-12 | **Facción** | Grupo con intereses comunes: equipo, club, familia, federación, patrocinador. |
| PER-13 | **Punto de vista (POV)** | Personaje cuya conciencia filtra la narración de una escena. |
| PER-14 | **Narrador** | Instancia que cuenta. Se define por persona, distancia, tiempo verbal y fiabilidad. Es distinto del POV. |
| PER-15 | **Distancia narrativa** | Grado de fusión entre la voz del narrador y la conciencia del POV, desde el sumario panorámico hasta el monólogo interior directo. |
| PER-16 | **Elenco activo** | Subconjunto de personajes con presencia en la ventana narrativa actual. Es el criterio primario de qué fichas entran en contexto. |

**Invariante PER-I1**: un personaje no puede actuar sobre información que no figure en su PER-10 en ese instante.
**Invariante PER-I2**: la voz de un personaje solo cambia como consecuencia de un evento registrado en su arco.

---

## 4. MUN — Mundo

| ID | Término | Definición |
|---|---|---|
| MUN-01 | **Lugar** | Espacio con identidad, geometría implícita y carga emocional. Reaparece y debe describirse de forma compatible. |
| MUN-02 | **Objeto significante** | Cosa física con función narrativa: trofeo, camiseta, carta, cicatriz. Candidato natural a símbolo. |
| MUN-03 | **Institución** | Organización con reglas propias: club, federación, prensa, patrocinador, escuela. |
| MUN-04 | **Regla del mundo** | Ley que el universo cumple siempre. En ficción realista coincide con la física y la normativa; en ficción especulativa se declara explícitamente. |
| MUN-05 | **Cronología** | Eje temporal absoluto del mundo, independiente del orden de narración. |
| MUN-06 | **Tiempo de mundo vs tiempo de relato** | Distinción entre cuándo ocurre algo y cuándo se cuenta. Analepsis y prolepsis solo son gestionables si ambos ejes están separados. |
| MUN-07 | **Evento histórico** | Suceso previo al inicio de la obra que condiciona el presente. Es canon aunque no se narre. |
| MUN-08 | **Léxico del mundo** | Vocabulario propio: apodos, jerga, nombres de lugares, términos técnicos. Debe usarse de forma consistente. |
| MUN-09 | **Textura sensorial** | Repertorio de detalles concretos asociados a un lugar o ambiente, para evitar descripciones genéricas e intercambiables. |
| MUN-10 | **Estado del mundo** | Fotografía consultable del universo en un instante: quién está dónde, qué posee cada uno, qué relaciones están vigentes, qué se sabe públicamente. |

---

## 5. DEP — Subdominio: épica deportiva

Esta capa es un **perfil** de la ontología: especializa las capas anteriores sin modificarlas. Sustituyéndola por otra (épica bélica, procedural judicial) el resto del modelo sigue en pie.

| ID | Término | Definición |
|---|---|---|
| DEP-01 | **Disciplina** | Deporte concreto. Determina reglamento, duración, roles y vocabulario técnico. |
| DEP-02 | **Reglamento** | Conjunto de reglas verificables de la disciplina. Actúa como MUN-04: violarlo rompe la verosimilitud de forma inmediata y detectable por el lector experto. |
| DEP-03 | **Competición** | Estructura de enfrentamientos: liga, copa, torneo, play-off. Define qué desenlaces son posibles. |
| DEP-04 | **Temporada** | Ciclo competitivo completo. Unidad natural de arco mayor en la épica deportiva. |
| DEP-05 | **Jornada** | Posición dentro del calendario de la competición. |
| DEP-06 | **Encuentro** | Partido, combate o carrera. Es una **secuencia** (EST-09) con estructura interna propia y resultado que altera el estado. |
| DEP-07 | **Resultado** | Marcador y consecuencias clasificatorias del encuentro. Dato duro, no negociable una vez escrito. |
| DEP-08 | **Clasificación** | Estado derivado del conjunto de resultados. Debe recalcularse, nunca narrarse de memoria. |
| DEP-09 | **Plantilla** | Conjunto de deportistas disponibles en `t`, con sus posiciones y estado físico. |
| DEP-10 | **Cuerpo técnico** | Entrenador, preparadores, médicos. Fuente habitual de mentor, antagonista interno o conflicto de autoridad. |
| DEP-11 | **Táctica** | Plan de juego. Objeto narrativo de primer orden: su elección expresa carácter y su fracaso genera crisis. |
| DEP-12 | **Estadística** | Métrica acumulada de un deportista o equipo. Es estado derivado y debe cuadrar con los encuentros narrados. |
| DEP-13 | **Estado físico** | Fatiga, lesión, recuperación, edad deportiva. Límite duro sobre PER-09. |
| DEP-14 | **Lesión** | Evento que degrada el estado físico durante una vigencia determinada. Reloj narrativo natural. |
| DEP-15 | **Rivalidad** | Relación de alta valencia negativa y larga vigencia entre deportistas, equipos o aficiones. Motor de la épica. |
| DEP-16 | **Afición y prensa** | Coro. Amplifica consecuencias, genera presión y permite narrar el impacto público de un hecho privado. |
| DEP-17 | **Dimensión económica** | Fichajes, contratos, patrocinios, descenso. Fuente de conflicto ajeno al juego. |
| DEP-18 | **Momento cumbre** | Instante decisivo de un encuentro: penalti, último asalto, última vuelta. Punto de máxima dilatación temporal permitida. |
| DEP-19 | **Verosimilitud deportiva** | Grado en que lo narrado es posible según DEP-02, DEP-09 y DEP-13. Dimensión de calidad propia de este subdominio. |
| DEP-20 | **Doble arco** | Principio estructural del género: el arco competitivo (¿ganan?) y el arco interno (¿se convierte en quien debe ser?) deben resolverse en momentos distintos. Resolverlos a la vez produce un final plano. |

**Invariante DEP-I1**: la clasificación y las estadísticas narradas deben ser recalculables a partir del registro de resultados.
**Invariante DEP-I2**: ningún deportista participa en un encuentro si su DEP-13 lo impide en esa fecha.

---

## 6. POE — Poética y estilo

| ID | Término | Definición |
|---|---|---|
| POE-01 | **Tema** | Pregunta moral que la obra plantea y responde con acciones, no con discursos. |
| POE-02 | **Motivo** | Elemento concreto que reaparece y acumula significado: una lesión en la rodilla, la lluvia, un número de dorsal. |
| POE-03 | **Símbolo** | Objeto o acción que representa de forma estable una idea del tema. |
| POE-04 | **Tono** | Actitud emocional dominante del texto: elegíaco, épico, irónico, seco. |
| POE-05 | **Registro** | Nivel de lengua: culto, coloquial, técnico, vulgar. Varía por POV y por escena. |
| POE-06 | **Guía de estilo** | Especificación operativa y verificable: tiempo verbal, persona, longitud media de frase, uso de adverbios, tratamiento del diálogo, prohibiciones explícitas. |
| POE-07 | **Ritmo (pacing)** | Relación entre tiempo de mundo y número de palabras. Se acelera con sumario y elipsis, se frena con escena y beat. |
| POE-08 | **Densidad** | Proporción de información nueva por párrafo. Baja densidad se percibe como relleno aunque la prosa sea correcta. |
| POE-09 | **Subtexto** | Lo que los personajes quieren decir y no dicen. Principal indicador de diálogo de calidad. |
| POE-10 | **Mostrar vs contar** | Elección entre dramatizar y resumir. No es una regla, es un presupuesto que se asigna por escena. |
| POE-11 | **Tic de modelo** | Patrón recurrente e involuntario propio de la generación automática: fórmulas de apertura y cierre, tríadas, contrastes del tipo "no X, sino Y", metáforas comodín. Antipatrón de estilo. |
| POE-12 | **Lista de proscripción** | Conjunto explícito de palabras, imágenes y construcciones vetadas para esta obra. Se alimenta de POE-11 y de las repeticiones ya detectadas en capítulos previos. |
| POE-13 | **Huella estilística** | Perfil cuantitativo del texto generado: distribución de longitud de frase, riqueza léxica, n-gramas frecuentes. Permite medir deriva de estilo. |
| POE-14 | **Autosimilitud** | Tendencia del sistema a reciclar sus propias imágenes y estructuras cuando lee su producción anterior. Degradación específica de la generación larga. |

---

## 7. CAN — Canon y continuidad

| ID | Término | Definición |
|---|---|---|
| CAN-01 | **Canon** | Conjunto de hechos verdaderos en el universo. Fuente única de verdad. Lo que no está en el canon no ha ocurrido. |
| CAN-02 | **Hecho canónico** | Afirmación atómica, fechada, atribuible y verificable. Ejemplo: "en la jornada 14 el protagonista se lesiona el ligamento cruzado". |
| CAN-03 | **Biblia de la obra (Story Bible)** | Documento estructurado que agrega canon, personajes, mundo, estilo y escaleta. Es el activo central del sistema. |
| CAN-04 | **Continuidad** | Propiedad de que todo lo narrado sea compatible con el canon vigente en ese punto. |
| CAN-05 | **Contradicción** | Par de afirmaciones canónicas incompatibles. Tipos frecuentes: de hecho, temporal, de conocimiento (PER-10), de capacidad (PER-09), de estado físico (DEP-13), de nombre. |
| CAN-06 | **Setup** | Elemento plantado con intención de rendir más adelante. |
| CAN-07 | **Payoff** | Rendimiento narrativo de un setup. |
| CAN-08 | **Deuda narrativa** | Conjunto de setups abiertos y promesas no cumplidas. Se mide, se prioriza y se salda antes del final. Es la métrica de salud estructural más útil en obra larga. |
| CAN-09 | **Prefiguración (foreshadowing)** | Setup de baja visibilidad, cuya función solo se reconoce en retrospectiva. |
| CAN-10 | **Retcon** | Reinterpretación deliberada de canon previo. Solo es legítima si es explícita, registrada y compatible con el texto ya escrito. |
| CAN-11 | **Delta canónico** | Conjunto de cambios de estado que produce un capítulo recién generado. Debe extraerse y validarse antes de considerar el capítulo cerrado. |
| CAN-12 | **Congelación (freeze)** | Estado de un capítulo aprobado: su prosa pasa a ser canon y ya no puede contradecirse, solo revisarse mediante un proceso explícito. |

**Invariante CAN-I1**: ningún capítulo se cierra sin que su CAN-11 esté extraído, validado e integrado.
**Invariante CAN-I2**: la deuda narrativa al final de la obra debe ser cero o estar declarada como continuidad hacia la siguiente entrega.

---

## 8. CTX — Contexto

Capa que conecta el dominio narrativo con la realidad técnica: **el modelo solo sabe lo que cabe en la llamada**.

Las filas van agrupadas por tema, no por número: los cinco términos de límite abren la tabla aunque sus números no sean correlativos.

| ID | Término | Definición |
|---|---|---|
| CTX-01 | **Ventana de contexto** | Techo de tokens de **entrada** de una llamada al modelo. En este sistema: **100.000 tokens**, fijados por el proyecto y no por el proveedor, cuyos modelos ofrecen entre 200.000 y 1.000.000. La salida no cuenta contra él y tiene tope propio. |
| CTX-02 | **Presupuesto de contexto** | Asignación deliberada de esa ventana entre categorías de información. Sin presupuesto explícito, el contexto se llena por inercia con lo más reciente. |
| CTX-18 | **Ocupación operativa** | Fracción de CTX-01 que se permite usar realmente en una llamada. Es deliberadamente inferior al límite físico, porque la distracción (CTX-14) y la dilución de atención aparecen mucho antes de agotar la ventana. |
| CTX-19 | **Desbordamiento** | Situación en que el material seleccionado supera la ocupación operativa. Dispara compactación (CTX-10) por orden inverso de prioridad, nunca truncamiento ciego por el final. |
| CTX-20 | **Techo de concurrencia** | Límite agregado de tokens de **entrada** que el sistema puede tener en vuelo en un mismo instante: **100.000**, sumando todas las llamadas simultáneas y sus cupos de tirón (CTX-22). Es una política del sistema, no un dato del proveedor: CTX-01 acota una llamada, CTX-20 acota cuántas se solapan. Con las llamadas en serie, cada una dispone del techo entero. Su dueño es el Orquestador. |
| CTX-21 | **Herramienta** | Capacidad que un agente de modelo invoca **durante su propio turno**, a diferencia de una skill, que ejecuta el código antes o después de la llamada. Ocupa ventana dos veces: su definición y el resultado de cada consulta. La lista de herramientas de un agente es cerrada. |
| CTX-22 | **Cupo de tirón** | Máximo de tokens que un agente puede acumular llamando a sus herramientas (CTX-21) durante un turno. Se reserva entero en la admisión y no se amplía en caliente; agotado, las herramientas niegan toda consulta y el agente concluye con lo que tiene. |
| CTX-23 | **Prefijo cacheable** | Tramo inicial de un paquete, idéntico en todas las llamadas de un agente, colocado al principio para que el proveedor lo sirva desde caché. Dos condiciones: nada voluble delante, porque el caché casa por prefijo y un byte distinto invalida todo lo que sigue; y tamaño por encima del mínimo cacheable del modelo, por debajo del cual no cachea y no avisa. |
| CTX-03 | **Paquete de contexto** | Conjunto ensamblado y ordenado de material que acompaña a una instrucción de generación concreta. Es un artefacto con identidad propia: se versiona, se inspecciona y se depura. |
| CTX-04 | **Ingeniería de contexto** | Disciplina de decidir qué información entra, en qué forma, en qué orden y con qué prioridad en cada llamada. En obra larga sustituye a la ingeniería de prompts como actividad principal. |
| CTX-05 | **Ficha compacta** | Faceta (MET-08) de una entidad reducida a lo mínimo accionable para una escena concreta. |
| CTX-06 | **Resumen jerárquico** | Cadena de resúmenes de granularidad creciente: escena → capítulo → arco → obra. Permite dar memoria completa a coste logarítmico. |
| CTX-07 | **Ventana literal reciente** | Fragmento de prosa anterior incluido sin resumir, para sostener voz, ritmo y micro-continuidad. |
| CTX-08 | **Recuperación (retrieval)** | Selección dinámica de fragmentos de canon o prosa relevantes para la escena que se va a escribir. |
| CTX-09 | **Recuperación híbrida** | Combinación de búsqueda semántica, búsqueda léxica y consulta estructurada al canon. Ninguna de las tres basta por sí sola: los nombres propios fallan en semántica y las relaciones fallan en léxica. |
| CTX-10 | **Compactación** | Sustitución de material extenso por su resumen cuando el presupuesto se agota, preservando los hechos canónicos y los hilos abiertos. |
| CTX-11 | **Aislamiento de contexto** | Ejecución de una subtarea en una ventana propia y limpia, devolviendo solo su resultado. Evita contaminar la ventana principal. |
| CTX-12 | **Deriva (drift)** | Alejamiento progresivo respecto a la guía de estilo, la voz o el plan, acumulado a lo largo de muchas generaciones encadenadas. |
| CTX-13 | **Envenenamiento de contexto** | Entrada de un dato falso en el contexto que se reutiliza y consolida como si fuera canon. Es el fallo más caro: se propaga. |
| CTX-14 | **Distracción de contexto** | Degradación por exceso de material irrelevante: el modelo atiende a lo accesorio y pierde la instrucción. |
| CTX-15 | **Conflicto de contexto** | Presencia simultánea de dos versiones incompatibles del mismo hecho, típicamente una obsoleta y una vigente. |
| CTX-16 | **Sesgo de recencia** | Tendencia a ponderar en exceso lo último del paquete. Se explota colocando la instrucción operativa al final. |
| CTX-17 | **Ancla** | Elemento repetido en todas las llamadas para frenar la deriva: guía de estilo, ficha de voz del POV, invariantes duros. Ocupa el prefijo cacheable (CTX-23). |

**Invariante CTX-I1**: en todo instante, la suma de la entrada de las llamadas en vuelo, cupos de tirón (CTX-22) incluidos, es menor o igual a CTX-20. Una llamada que no quepa se encola; nunca se admite recortándola.

---

## 9. CAL — Calidad

| ID | Término | Definición |
|---|---|---|
| CAL-01 | **Dimensión de calidad** | Eje independiente de evaluación. Ver tabla inferior. |
| CAL-02 | **Rúbrica** | Definición operativa de una dimensión con niveles y ejemplos, de modo que dos evaluadores distintos coincidan. |
| CAL-03 | **Verificador determinista** | Comprobación ejecutable sin modelo: fechas, marcadores, clasificación, nombres, longitud, tiempo verbal, repetición de n-gramas. Barato, exacto y de cobertura limitada. |
| CAL-04 | **Juez LLM** | Evaluador basado en modelo para dimensiones subjetivas. Requiere rúbrica, evidencia citada y aislamiento respecto del generador. |
| CAL-05 | **Defecto** | Incumplimiento concreto y localizado de una rúbrica o invariante. |
| CAL-06 | **Severidad** | S1 rompe canon o reglamento. S2 daña el arco o la caracterización. S3 afecta a estilo o ritmo. S4 cosmético. |
| CAL-07 | **Puerta de calidad** | Punto del proceso donde un artefacto no avanza si no supera un umbral. |
| CAL-08 | **Regeneración dirigida** | Reescritura de un fragmento con el defecto y su evidencia en el contexto, en lugar de repetir la generación completa a ciegas. |
| CAL-09 | **Umbral de aceptación** | Valor mínimo por dimensión. Distinto por dimensión: continuidad admite cero defectos S1; ritmo admite variación. |
| CAL-10 | **Conjunto dorado** | Colección fija de fragmentos con defectos conocidos y sembrados, usada para verificar que los jueces siguen detectando lo que deben. Sustituye a la calibración por revisión manual. |
| CAL-11 | **Jurado** | Varias instancias de juez con rúbricas o semillas distintas evaluando lo mismo. La dispersión entre ellas mide la fiabilidad de la puntuación: dispersión alta invalida el veredicto y fuerza verificación adicional. |
| CAL-12 | **Presupuesto de reintentos** | Número máximo de regeneraciones dirigidas sobre un mismo artefacto. Al agotarse no hay escalado a persona: se replanifica la escena o el arco con restricciones más estrictas. |
| CAL-13 | **Cuarentena** | Estado de un artefacto que no supera sus puertas tras agotar CAL-12. Queda marcado, no bloquea la producción y entra en la cola de replanificación automática. |

**Dimensiones de calidad (CAL-01)**

| # | Dimensión | Verificable por |
|---|---|---|
| 1 | Continuidad factual y temporal | Determinista + canon; juez LLM solo para la continuidad de lectura |
| 2 | Consistencia de caracterización y voz | Mixto |
| 3 | Integridad estructural y causalidad | Mixto |
| 4 | Tensión, ritmo y densidad | Juez LLM |
| 5 | Fidelidad a la guía de estilo | Determinista + juez |
| 6 | Verosimilitud del subdominio (DEP-19) | Determinista + experto |
| 7 | No redundancia y frescura de imagen | Determinista (n-gramas, POE-13) |
| 8 | Calidad de diálogo y subtexto | Juez LLM |
| 9 | Resonancia temática | Jurado de jueces LLM · CAL-11 |
| 10 | Cumplimiento del brief y restricciones | Determinista; juez LLM para la personalización natural |

---

## 10. PRO — Proceso

| ID | Término | Definición |
|---|---|---|
| PRO-01 | **Brief** | Encargo inicial: género, tono, extensión, público, restricciones. |
| PRO-02 | **Premisa** | Situación inicial más pregunta dramática, en una frase. |
| PRO-03 | **Logline** | Formulación comercial de la premisa. |
| PRO-04 | **Sinopsis** | Resumen del recorrido completo incluyendo el final. |
| PRO-05 | **Tratamiento** | Desarrollo intermedio entre sinopsis y escaleta, con arcos y actos. |
| PRO-06 | **Borrador** | Prosa generada de un capítulo, aún no congelada. |
| PRO-07 | **Pase** | Recorrido completo sobre el texto con un objetivo único: continuidad, voz, ritmo, poda. Varios pases estrechos superan a un pase general. |
| PRO-08 | **Versión** | Instantánea identificable de un artefacto, con su paquete de contexto asociado. |
| PRO-09 | **Trazabilidad** | Capacidad de reconstruir qué contexto y qué instrucción produjeron un fragmento concreto. Condición para depurar una obra larga. |
| PRO-10 | **Política de arbitraje** | Conjunto de reglas de precedencia que resuelve conflictos sin intervención externa: canon congelado gana sobre delta nuevo, brief gana sobre canon derivado, invariante duro gana sobre preferencia estética. Todo arbitraje queda registrado. |
| PRO-11 | **Autonomía de extremo a extremo** | El sistema decide, verifica, corrige y cierra sin aprobación externa. Toda decisión que en un flujo asistido correspondería a una persona debe tener aquí una regla explícita, un umbral o un agente responsable. |
| PRO-12 | **Replanificación** | Reacción a un bloqueo persistente: en vez de pedir ayuda, se reescribe la especificación de la escena o se recalcula el tramo de escaleta afectado y se vuelve a generar. |
| PRO-13 | **Memoria de trabajo** | Material vivo de un capítulo en curso: borradores, defectos abiertos con su evidencia, veredictos del jurado, cuenta de reintentos y cola de admisión. Nace al planificar el capítulo y muere al congelarlo. **Nunca entra en la ventana de un modelo**: es lo que el sistema sostiene mientras produce, no lo que el agente ve. |
| PRO-14 | **Punto de reanudación** | Última frontera cerrada desde la que una tirada interrumpida continúa sin rehacer trabajo ya validado. En este sistema es la escena, porque es la unidad de reintento (PRO-07, CAL-12). |

**Invariante PRO-I1**: al congelar un capítulo no queda ninguna fila de memoria de trabajo asociada a él. Lo que era verdad pasó al canon; lo que fue proceso vive en la traza, no en el fichero de la novela.
**Invariante PRO-I2**: una tirada solo reanuda desde un punto de reanudación cerrado. El material posterior a ese punto se descarta, nunca se reaprovecha a medias.

---

## 11. Términos ambiguos

Evitar sin cualificar:

- **"Memoria"**: usar CTX-06, CTX-08 o CAN-03 según lo que se quiera decir.
- **"Capítulo"** como sinónimo de escena: son EST-07 y EST-08, con unidades de control distintas.
- **"Coherencia"** a secas: separar coherencia factual (CAN-04) de coherencia estilística (CTX-12).
- **"Contexto"** a secas: separar contexto narrativo (situación en la ficción) de contexto de modelo (CTX-03).
- **"Historia"**: separar fábula (orden cronológico) de trama (orden de narración), ver MUN-06.
