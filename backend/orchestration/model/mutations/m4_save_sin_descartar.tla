------------------------------ MODULE m4_save_sin_descartar ------------------------------
\* MUTACION m4_save_sin_descartar: checkpoint.save no borra los borradores posteriores
\* Copia de run.tla con un solo cambio, marcado MUTACION. Debe dar contraejemplo.
(***************************************************************************)
(* La tirada completa. VER-18, `verification.md` §5.10.                    *)
(*                                                                         *)
(* configuracion -> planificacion -> N capitulos (cada uno, el ciclo de    *)
(* vida de chapter.tla) -> cierre de obra, con caida y reanudacion desde   *)
(* el punto de reanudacion, y enmiendas del lector que publican la version *)
(* N+1 entre congelaciones. Tal como lo ejecutan `orchestration/loop.py`   *)
(* (`run`), `orchestration/checkpoint.py` y `orchestration/amend.py`.      *)
(*                                                                         *)
(* El capitulo no se reescribe: se instancia chapter.tla y se reutilizan   *)
(* sus acciones. Solo se envuelven las que tocan algo que sobrevive a una  *)
(* caida (borradores, punto de reanudacion, canon, versiones).             *)
(*                                                                         *)
(* Cuatro banderas eligen entre el codigo de hoy (FALSE) y el arreglo que  *)
(* propone el README (TRUE). run.cfg las pone a TRUE; los .cfg de          *)
(* code-today/ ponen una a FALSE y dan el contraejemplo de su fallo.       *)
(*                                                                         *)
(* Prueba el flujo modelado, no el orquestador que lo implementa: esa      *)
(* distancia la cubre VER-05.                                              *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS Scenes, SceneAttempts, ChapterAttempts, ArcReplans,   \* chapter.tla
          Ceiling, Reserve, Jurors, JuryReserve,                \* chapter.tla
          Chapters,          \* capitulos de la tirada. Numero de modelo
          PlanAttempts,      \* 3: `_plan_with_gate` aborta con arc_replans > 2
          MaxCrashes,        \* caidas como mucho. Numero de modelo, no del codigo
          MaxAmends,         \* solicitudes del lector como mucho. Numero de modelo
          \* Las cuatro correcciones. FALSE es el codigo de hoy.
          CheckpointOnlyPassed, \* el punto solo avanza con escenas que pasaron
          ResumeSkipsFrozen,    \* reanudar no reescribe un capitulo ya congelado
          ResumeKeepsBudget,    \* reanudar conserva los intentos consumidos, §7.4
          RetconKeepsHistory    \* un retcon guarda el texto que ven las versiones viejas

\* Las del capitulo, con sus nombres, para que INSTANCE las comparta.
VARIABLES state, scene, sceneAttempts, chapterAttempts, arcReplans,
          canonWritten, gatesPassed, juryPassed, openS1, deltaClean, repaired,
          inFlight, jurorsIn, jurorsDone, retcons, lastClosed

\* Las de la tirada.
VARIABLES phase,        \* fase de la tirada
          chap,         \* capitulo en curso
          planTries,    \* intentos de escaleta consumidos en esta planificacion
          scenesOk,     \* toda escena de este intento paso su puerta de verdad
          drafts,       \* wm_draft del capitulo: "none", "ok" o "bad" por escena
          ckCh, ckScene,\* wm_run_state: capitulo y ultima escena cerrada
          freezes,      \* veces que el bucle congelo cada capitulo
          revs,         \* por capitulo, una entrada por texto congelado: paso sus puertas
          hist,         \* scene_text_history por capitulo: <<until_version, revision>>
          touched,      \* capitulos ya reescritos mientras la version vigente lo es
          cv,           \* version vigente del manuscrito
          vmax,         \* max_chapter de cada version creada por enmienda
          snap,         \* lo que mostraba cada version cuando dejo de ser la vigente
          queue,        \* solicitudes en cola (queued o applying)
          requested,    \* solicitudes creadas en total
          crashes,      \* caidas ocurridas
          spentCh,      \* fantasma: intentos de capitulo gastados, caidas incluidas
          spentArc      \* fantasma: replanificaciones de tramo gastadas, caidas incluidas

chVars  == << state, scene, sceneAttempts, chapterAttempts, arcReplans,
              canonWritten, gatesPassed, juryPassed, openS1, deltaClean, repaired,
              inFlight, jurorsIn, jurorsDone, retcons, lastClosed >>
runVars == << phase, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes, revs,
              hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>
vars    == << chVars, runVars >>

Ch == INSTANCE chapter

Phases   == { "Configuring", "Planning", "Running", "Between", "Closing",
              "Crashed", "Published", "Unclosed", "Aborted" }
Terminal == { "Published", "Unclosed", "Aborted" }
Versions == 1..(MaxAmends + 1)
Frozen   == { c \in 1..Chapters : freezes[c] >= 1 }
MaxOf(S) == IF S = {} THEN 0 ELSE CHOOSE m \in S : \A x \in S : x <= m
NoDrafts == [ i \in 1..Scenes |-> "none" ]

\* Lo que ve el lector de la version v: `manuscript.chapters_in` y `text_at`.
ChaptersIn(v) == IF v = cv THEN Frozen ELSE { c \in Frozen : c <= vmax[v + 1] }
View(v, c) ==
    LET E == { e \in hist[c] : e[1] >= v }
    IN  IF E = {} THEN Len(revs[c])
        ELSE (CHOOSE e \in E : \A f \in E : e[1] <= f[1])[2]

\* Reescribir un capitulo congelado: retcon o enmienda. `keep` guarda el texto
\* anterior para las versiones que ya no son la vigente.
\* La reescritura conserva la marca de puertas del capitulo: reverifica los
\* pasajes que toca, no aprueba los que no toca.
Rewrite(T, keep, until) ==
    /\ revs' = [ c \in 1..Chapters |->
                   IF c \in T THEN Append(revs[c], revs[c][Len(revs[c])]) ELSE revs[c] ]
    /\ hist' = [ c \in 1..Chapters |->
                   IF c \in T /\ keep /\ ~(\E e \in hist[c] : e[1] = until)
                     THEN hist[c] \cup { << until, Len(revs[c]) >> }
                     ELSE hist[c] ]

\* Las escenas congeladas que un retcon o una enmienda reescriben, por capitulo.
\* Ninguno o uno: basta para los contraejemplos y mantiene el modelo pequeno.
Targets == { {} } \cup { {c} : c \in Frozen }

\* Reduccion del espacio de estados, sin perder nada que un invariante mire.
\* Un retcon con la version 1 vigente no tiene version vieja que alterar, y una
\* segunda reescritura del mismo capitulo en la misma version deja las vistas
\* igual que la primera. Ninguna de las dos se explora.
RetconTargets ==
    IF cv = 1 THEN { {} } ELSE { {} } \cup { {c} : c \in Frozen \ touched }

\* El capitulo en su estado inicial, desde la escena `from` y con el presupuesto
\* dado. Es `Init` de chapter.tla con la escena y los contadores como parametro.
Fresh(from, chAtt, arcAtt) ==
    /\ state' = IF from > Scenes THEN "ChapterGate" ELSE "Writing"
    /\ scene' = IF from > Scenes THEN Scenes ELSE from
    /\ lastClosed' = from - 1
    /\ sceneAttempts' = 0 /\ chapterAttempts' = chAtt /\ arcReplans' = arcAtt
    /\ canonWritten' = FALSE /\ gatesPassed' = FALSE /\ juryPassed' = FALSE
    /\ openS1' = FALSE /\ deltaClean' = FALSE /\ repaired' = FALSE
    /\ inFlight' = 0 /\ jurorsIn' = 0 /\ jurorsDone' = 0 /\ retcons' = 0

\* Los fantasmas siguen a los contadores de la escalera; solo Resume los separa.
Ghost ==
    /\ spentArc' = IF arcReplans' > arcReplans THEN spentArc + 1 ELSE spentArc
    /\ spentCh'  = IF arcReplans' > arcReplans THEN 0
                   ELSE IF chapterAttempts' > chapterAttempts THEN spentCh + 1
                   ELSE spentCh

Init ==
    /\ state = "Writing" /\ scene = 1 /\ lastClosed = 0
    /\ sceneAttempts = 0 /\ chapterAttempts = 0 /\ arcReplans = 0
    /\ canonWritten = FALSE /\ gatesPassed = FALSE /\ juryPassed = FALSE
    /\ openS1 = FALSE /\ deltaClean = FALSE /\ repaired = FALSE
    /\ inFlight = 0 /\ jurorsIn = 0 /\ jurorsDone = 0 /\ retcons = 0
    /\ phase = "Configuring" /\ chap = 1 /\ planTries = 0 /\ scenesOk = TRUE
    /\ drafts = NoDrafts /\ ckCh = 1 /\ ckScene = 0
    /\ freezes = [ c \in 1..Chapters |-> 0 ]
    /\ revs = [ c \in 1..Chapters |-> << >> ]
    /\ hist = [ c \in 1..Chapters |-> {} ]
    /\ touched = {}
    /\ cv = 1
    /\ vmax = [ v \in Versions |-> 0 ]
    /\ snap = [ v \in Versions |-> [ c \in 1..Chapters |-> 0 ] ]
    /\ queue = 0 /\ requested = 0 /\ crashes = 0 /\ spentCh = 0 /\ spentArc = 0

(* ----------------------------------------------------------------------- *)
(* Configuracion y planificacion                                           *)

\* `canon.brief.create_novel`: el brief valido crea la novela; el invalido no.
Configure ==
    /\ phase = "Configuring"
    /\ phase' = "Planning"
    /\ UNCHANGED << chVars, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

ConfigRejected ==
    /\ phase = "Configuring"
    /\ phase' = "Aborted"
    /\ UNCHANGED << chVars, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

\* `_plan_with_gate`: la escaleta no pasa outline.check y se reintenta.
PlanFails ==
    /\ phase = "Planning"
    /\ planTries + 1 < PlanAttempts
    /\ planTries' = planTries + 1
    /\ UNCHANGED << chVars, phase, chap, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

PlanAborts ==
    /\ phase = "Planning"
    /\ planTries + 1 >= PlanAttempts
    /\ phase' = "Aborted"
    /\ UNCHANGED << chVars, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

\* La escaleta pasa y la tirada sigue desde el punto de reanudacion: `run`,
\* `load(path) or ResumePoint(chapter=1)`, y la reutilizacion de borradores de
\* `_write_chapter`, que reutiliza todo borrador que encuentre del capitulo.
Reusable == MaxOf({ k \in 0..Scenes : \A i \in 1..k : drafts[i] /= "none" })

PlanPasses ==
    /\ phase = "Planning"
    /\ chap' = ckCh
    /\ planTries' = 0
    /\ IF ckCh > Chapters
         THEN /\ phase' = "Closing"
              /\ UNCHANGED << chVars, scenesOk >>
       ELSE IF ResumeSkipsFrozen /\ freezes[ckCh] >= 1
         \* Arreglo: el capitulo ya esta congelado; se sigue en su puerta de acto.
         THEN /\ phase' = "Running"
              /\ state' = "Frozen" /\ scene' = Scenes /\ lastClosed' = Scenes
              /\ canonWritten' = TRUE /\ gatesPassed' = TRUE /\ juryPassed' = TRUE
              /\ deltaClean' = TRUE /\ scenesOk' = TRUE
              /\ UNCHANGED << sceneAttempts, chapterAttempts, arcReplans, openS1,
                              repaired, inFlight, jurorsIn, jurorsDone, retcons >>
       ELSE /\ phase' = "Running"
            \* RF-107, `may_start_chapter`: el anterior tiene que estar congelado.
            /\ IF ckCh = 1 THEN TRUE ELSE freezes[ckCh - 1] >= 1
            /\ scenesOk' = \A i \in 1..Reusable : drafts[i] = "ok"
            /\ IF ResumeKeepsBudget
                 THEN Fresh(Reusable + 1, spentCh, spentArc)
                 ELSE Fresh(Reusable + 1, 0, 0)       \* `Budget()` en `run`
    /\ UNCHANGED << drafts, ckCh, ckScene, freezes, revs, hist, touched, cv, vmax, snap,
                    queue, requested, crashes, spentCh, spentArc >>

(* ----------------------------------------------------------------------- *)
(* El capitulo: las acciones de chapter.tla                                *)

\* Las que no tocan nada persistente se reutilizan tal cual.
ChapterStep ==
    /\ phase = "Running"
    /\ \/ Ch!WriteScene \/ Ch!SceneFailsRetry \/ Ch!SceneFailsRespec
       \/ Ch!ChapterGatePasses \/ Ch!ChapterGateFails
       \/ Ch!JurorAdmitted \/ Ch!JurorReturns \/ Ch!JuryPasses \/ Ch!JuryFails
       \/ Ch!Polish \/ Ch!Reverify \/ Ch!Repair \/ Ch!Revalidate
       \/ Ch!Extract \/ Ch!DeltaAccepted \/ Ch!DeltaRejected
       \/ Ch!RetconProposed \/ Ch!RetconRefused
       \/ Ch!Supervise
       \/ Ch!QuarantineRespec \/ Ch!QuarantineReplan
    /\ Ghost
    /\ UNCHANGED << phase, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes >>

\* Una escena pasa: `drafts.save_draft` y `checkpoint.save`, que borra lo posterior.
ScenePasses ==
    /\ phase = "Running"
    /\ Ch!ScenePasses
    /\ drafts' = [ drafts EXCEPT ![scene] = "ok" ]   \* MUTACION: sin DELETE
    /\ ckScene' = scene
    /\ UNCHANGED << phase, chap, planTries, scenesOk, ckCh, freezes, revs, hist, touched, cv,
                    vmax, snap, queue, requested, crashes, spentCh, spentArc >>

\* La escena agota su escalera. El codigo guarda su borrador y avanza el punto
\* igual que si hubiera pasado (`_write_chapter`, tras `_write_scene`).
SceneFailsEscalate ==
    /\ phase = "Running"
    /\ Ch!SceneFailsEscalate
    /\ IF CheckpointOnlyPassed
         THEN UNCHANGED << drafts, ckScene >>
         ELSE /\ drafts' = [ i \in 1..Scenes |-> IF i = scene THEN "bad"
                                                 ELSE IF i > scene THEN "none" ELSE drafts[i] ]
              /\ ckScene' = scene
    /\ UNCHANGED << phase, chap, planTries, scenesOk, ckCh, freezes, revs, hist, touched, cv,
                    vmax, snap, queue, requested, crashes, spentCh, spentArc >>

\* El Archivero devuelve tres deltas vacios: EmptyDeltaError, la tirada acaba.
ExtractEmpty ==
    /\ phase = "Running"
    /\ state = "Extracting"
    /\ phase' = "Aborted"
    /\ UNCHANGED << chVars, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

\* Un retcon reescribe escenas ya congeladas (`_try_retcon`, `refreeze.commit`).
\* El codigo no guarda su texto anterior: RetconKeepsHistory es el arreglo.
RetconApplied ==
    /\ phase = "Running"
    /\ Ch!RetconApplied
    /\ \E T \in RetconTargets :
         Rewrite(T, RetconKeepsHistory /\ cv > 1, cv - 1) /\ touched' = touched \cup T
    /\ UNCHANGED << phase, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

RetconPartial ==
    /\ phase = "Running"
    /\ Ch!RetconPartial
    /\ \E T \in RetconTargets :
         Rewrite(T, RetconKeepsHistory /\ cv > 1, cv - 1) /\ touched' = touched \cup T
    /\ UNCHANGED << phase, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

\* `_freeze` y `commit_chapter`: el canon se escribe y la memoria de trabajo del
\* capitulo se purga. El punto de reanudacion no cambia (`checkpoint.clear`).
Freeze ==
    /\ phase = "Running"
    /\ Ch!Freeze
    /\ freezes' = [ freezes EXCEPT ![chap] = @ + 1 ]
    /\ revs' = [ revs EXCEPT ![chap] =
                   Append(@, scenesOk /\ gatesPassed /\ juryPassed /\ deltaClean) ]
    /\ drafts' = NoDrafts
    /\ UNCHANGED << phase, chap, planTries, scenesOk, ckCh, ckScene, hist, touched, cv, vmax,
                    snap, queue, requested, crashes, spentCh, spentArc >>

\* Tras congelar, la puerta de acto y el Supervisor pueden replanificar; si la
\* replanificacion no pasa `outline.check`, `_replan` lanza RunAbortedError.
PostFreezeAborts ==
    /\ phase = "Running"
    /\ state = "Frozen"
    /\ phase' = "Aborted"
    /\ UNCHANGED << chVars, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

\* Sin cuarto nivel: RunAbortedError.
QuarantineAbort ==
    /\ phase = "Running"
    /\ Ch!QuarantineAbort
    /\ phase' = "Aborted"
    /\ UNCHANGED << chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes, revs,
                    hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

\* `save(path, ResumePoint(chapter=numero + 1))`, tras supervisar.
SaveNext ==
    /\ phase = "Running"
    /\ state = "Supervised"
    /\ ckCh' = chap + 1 /\ ckScene' = 0
    /\ phase' = "Between"
    /\ UNCHANGED << chVars, chap, planTries, scenesOk, drafts, freezes, revs, hist, touched, cv,
                    vmax, snap, queue, requested, crashes, spentCh, spentArc >>

\* Drenadas las enmiendas, el capitulo siguiente, o el cierre tras el ultimo.
StartChapter ==
    /\ phase = "Between"
    /\ queue = 0
    /\ chap < Chapters
    /\ freezes[chap] >= 1                   \* RF-107, `may_start_chapter`
    /\ chap' = chap + 1
    /\ phase' = "Running"
    /\ scenesOk' = TRUE
    /\ Fresh(1, 0, 0)
    /\ spentCh' = 0 /\ spentArc' = 0
    /\ UNCHANGED << planTries, drafts, ckCh, ckScene, freezes, revs, hist, touched, cv, vmax,
                    snap, queue, requested, crashes >>

ToClose ==
    /\ phase = "Between"
    /\ queue = 0
    /\ chap = Chapters
    /\ phase' = "Closing"
    /\ UNCHANGED << chVars, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

\* `_work_closes`: las cuatro condiciones de RF-23. Si no se cumplen, la tirada
\* acaba con closed=False y su motivo.
WorkCloses ==
    /\ phase = "Closing"
    /\ phase' = "Published"
    /\ UNCHANGED << chVars, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

WorkNotClosed ==
    /\ phase = "Closing"
    /\ phase' = "Unclosed"
    /\ UNCHANGED << chVars, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

(* ----------------------------------------------------------------------- *)
(* Caida y reanudacion                                                     *)

\* El proceso muere. Se pierde lo que estaba en memoria: el capitulo en curso y
\* el presupuesto. Sobrevive lo que esta en el fichero: borradores, punto,
\* canon, versiones y solicitudes (una en applying vuelve a queued, RF-226).
Crash ==
    /\ phase \in { "Planning", "Running", "Between", "Closing" }
    /\ crashes < MaxCrashes
    /\ crashes' = crashes + 1
    /\ phase' = "Crashed"
    /\ planTries' = 0 /\ scenesOk' = TRUE
    /\ Fresh(1, 0, 0)
    /\ UNCHANGED << chap, drafts, ckCh, ckScene, freezes, revs, hist, touched, cv, vmax, snap,
                    queue, requested, spentCh, spentArc >>

\* Se relanza la tirada: `run` vuelve a planificar y lee el punto (PlanPasses).
Resume ==
    /\ phase = "Crashed"
    /\ phase' = "Planning"
    /\ UNCHANGED << chVars, chap, planTries, scenesOk, drafts, ckCh, ckScene, freezes,
                    revs, hist, touched, cv, vmax, snap, queue, requested, crashes, spentCh, spentArc >>

(* ----------------------------------------------------------------------- *)
(* Enmiendas del lector: la regeneracion por cambio del lector             *)

\* RI-47, `create_request`: la solicitud queda en cola. La pide alguien de fuera.
AmendRequested ==
    /\ phase /= "Configuring"
    /\ requested < MaxAmends
    /\ requested' = requested + 1
    /\ queue' = queue + 1
    /\ UNCHANGED << chVars, phase, chap, planTries, scenesOk, drafts, ckCh, ckScene,
                    freezes, revs, hist, touched, cv, vmax, snap, crashes, spentCh, spentArc >>

\* Solo entre congelaciones (`after_freeze`, RF-223) o sin tirada en marcha
\* (`amend_novel` y `drain`).
AmendWindow == phase \in { "Between" } \cup Terminal

\* `_apply` y `commit_amendment`: reescribe, guarda el texto anterior hasta la
\* version vigente, y crea la N+1. Una reescritura con S1 se rechaza entera.
AmendApplied ==
    /\ AmendWindow
    /\ queue > 0
    /\ queue' = queue - 1
    /\ \E T \in Targets :
         /\ Rewrite(T, TRUE, cv)
         /\ touched' = T
         /\ cv' = cv + 1
         /\ vmax' = [ vmax EXCEPT ![cv + 1] = MaxOf(Frozen) ]
         /\ snap' = [ snap EXCEPT ![cv] =
                        [ c \in 1..Chapters |-> IF c \in Frozen THEN View(cv, c) ELSE 0 ] ]
    /\ UNCHANGED << chVars, phase, chap, planTries, scenesOk, drafts, ckCh, ckScene,
                    freezes, requested, crashes, spentCh, spentArc >>

\* RejectedError: `_reject`, la version no cambia.
AmendRejected ==
    /\ AmendWindow
    /\ queue > 0
    /\ queue' = queue - 1
    /\ UNCHANGED << chVars, phase, chap, planTries, scenesOk, drafts, ckCh, ckScene,
                    freezes, revs, hist, touched, cv, vmax, snap, requested, crashes, spentCh, spentArc >>

Done ==
    /\ phase \in Terminal
    /\ queue = 0
    /\ UNCHANGED vars

(* ----------------------------------------------------------------------- *)

\* Todo lo que hace avanzar la tirada. Crash y AmendRequested no estan: vienen
\* de fuera, pueden no ocurrir nunca, y exigirles equidad seria obligar al
\* sistema a caerse. Done es un tartamudeo y tampoco cuenta.
Progress ==
    \/ Configure \/ ConfigRejected \/ PlanFails \/ PlanAborts \/ PlanPasses
    \/ ChapterStep \/ ScenePasses \/ SceneFailsEscalate \/ ExtractEmpty
    \/ RetconApplied \/ RetconPartial \/ Freeze \/ PostFreezeAborts \/ QuarantineAbort
    \/ SaveNext \/ StartChapter \/ ToClose \/ WorkCloses \/ WorkNotClosed
    \/ Resume \/ AmendApplied \/ AmendRejected

Next == Progress \/ Crash \/ AmendRequested \/ Done

\* Equidad debil sobre Progress: si la tirada puede avanzar, avanza. Basta la
\* debil porque ninguna accion de Progress se desactiva y reactiva sin fin:
\* cada una consume un contador acotado o avanza de fase.
Spec == Init /\ [][Next]_vars /\ WF_vars(Progress)

(* ----------------------------------------------------------------------- *)
(* Invariantes de seguridad                                                *)

TypeOK ==
    /\ phase \in Phases
    /\ chap \in 1..(Chapters + 1) /\ ckCh \in 1..(Chapters + 1) /\ ckScene \in 0..Scenes
    /\ drafts \in [ 1..Scenes -> { "none", "ok", "bad" } ]
    /\ cv \in Versions /\ queue \in 0..MaxAmends /\ crashes \in 0..MaxCrashes
    /\ Ch!TypeOK

\* 1. Nunca se publica una version con un capitulo que no paso todas las
\* puertas: la de escena, la de capitulo, el Jurado y el arbitraje del delta.
NeverPublishUngated ==
    \A v \in 1..cv : \A c \in ChaptersIn(v) : revs[c][View(v, c)]

\* 2a. La reanudacion no duplica: ningun capitulo se congela dos veces.
NoChapterDuplicated == \A c \in 1..Chapters : freezes[c] <= 1

\* 2b. La reanudacion no pierde: lo anterior al capitulo en curso esta
\* congelado, y al cerrar lo esta todo.
NoChapterLost ==
    /\ phase \in { "Running", "Between" } => \A c \in 1..(chap - 1) : freezes[c] >= 1
    /\ phase \in { "Closing", "Published", "Unclosed" } => \A c \in 1..Chapters : freezes[c] >= 1

\* 2c. PRO-I2. El punto de reanudacion solo cubre escenas cerradas que pasaron
\* su puerta, y no hay borrador posterior a el. Es lo que Resume reutiliza.
ResumeOnlyClosed ==
    \A i \in 1..Scenes :
        /\ i <= ckScene => drafts[i] \in { "none", "ok" }
        /\ i >  ckScene => drafts[i] = "none"

\* 3. La version anterior se conserva tras una regeneracion: lo que mostraba
\* cada version al dejar de ser la vigente es lo que sigue mostrando.
PreviousVersionPreserved ==
    \A v \in 1..(cv - 1) : \A c \in ChaptersIn(v) : View(v, c) = snap[v][c]

\* 4. Los reintentos nunca superan el limite, tampoco sumando caidas.
RetriesWithinLimit ==
    /\ Ch!LadderBounded /\ Ch!RetconsBounded
    /\ planTries < PlanAttempts
    /\ spentCh < ChapterAttempts /\ spentArc <= ArcReplans

\* Los de chapter.tla, dentro de la tirada.
ChapterSafety ==
    phase = "Running" =>
        /\ Ch!NeverFreezeWithoutGates /\ Ch!NoCanonBeforeFreeze
        /\ Ch!RepairRevalidates /\ Ch!CtxI1

\* Comprobacion de alcance: TLC tiene que violarla. Si no, Published es inalcanzable.
NeverPublished == phase /= "Published"

(* ----------------------------------------------------------------------- *)
(* Liveness                                                                *)

\* Toda generacion termina publicando o con error.
GenerationTerminates == <>(phase \in Terminal)

\* Toda solicitud en cola acaba aplicada o rechazada.
AmendmentsSettle == [](queue > 0 => <>(queue = 0))

=============================================================================
