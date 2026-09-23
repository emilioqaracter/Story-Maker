---------------------------- MODULE chapter ----------------------------
(***************************************************************************)
(* El ciclo de vida del capitulo. VER-18, `verification.md` §5.10.         *)
(*                                                                         *)
(* Modela el flujo de `architecture.md` §7.1 a §7.3 tal como lo ejecuta    *)
(* `orchestration/loop.py`: escenas en serie con su puerta, puerta de      *)
(* capitulo, Jurado de tres instancias en paralelo, pase de estilo con     *)
(* reversion, delta y arbitraje con retcon, congelacion, supervision, y la *)
(* escalera de cuarentena de tres peldanos. RF-161.                        *)
(*                                                                         *)
(* Prueba el flujo modelado, no el orquestador que lo implementa: esa       *)
(* distancia la cubre VER-05.                                              *)
(***************************************************************************)
EXTENDS Naturals

CONSTANTS Scenes,          \* numero de escenas del capitulo
          SceneAttempts,   \* 3, RF-18
          ChapterAttempts, \* 2, RF-18
          ArcReplans,      \* 1, RF-18
          Ceiling,         \* 100000, CTX-20
          Reserve,         \* lo que reserva la llamada en serie mas grande
          Jurors,          \* 3, D-37
          JuryReserve      \* lo que reserva cada instancia del Jurado

VARIABLES state,           \* fase del ciclo
          scene,           \* escena en curso
          sceneAttempts, chapterAttempts, arcReplans,
          canonWritten,    \* se escribio el canon de este capitulo
          gatesPassed,     \* la puerta de capitulo paso en este intento
          juryPassed,      \* el Jurado paso en este intento
          openS1,          \* el pase de estilo abrio un S1 aun sin revertir
          deltaClean,      \* el delta valido sin rechazos
          repaired,        \* hubo reparacion pendiente de revalidar
          inFlight,        \* tokens de entrada en vuelo, CTX-I1
          jurorsIn,        \* instancias del Jurado admitidas y en vuelo
          jurorsDone,      \* instancias del Jurado que ya devolvieron
          retcons,         \* retcons aplicados por este capitulo
          lastClosed       \* ultima escena cerrada, PRO-14

vars == << state, scene, sceneAttempts, chapterAttempts, arcReplans,
           canonWritten, gatesPassed, juryPassed, openS1, deltaClean, repaired,
           inFlight, jurorsIn, jurorsDone, retcons, lastClosed >>

States == { "Writing", "SceneGate", "ChapterGate", "Judging", "Polishing",
            "Reverifying", "Repairing", "Revalidating", "Extracting",
            "Arbitrating", "Retconning", "Freezing", "Frozen", "Supervised",
            "Quarantine", "Aborted" }

Init ==
    /\ state = "Writing"
    /\ scene = 1
    /\ sceneAttempts = 0 /\ chapterAttempts = 0 /\ arcReplans = 0
    /\ canonWritten = FALSE
    /\ gatesPassed = FALSE
    /\ juryPassed = FALSE
    /\ openS1 = FALSE
    /\ deltaClean = FALSE
    /\ repaired = FALSE
    /\ inFlight = 0
    /\ jurorsIn = 0 /\ jurorsDone = 0
    /\ retcons = 0
    /\ lastClosed = 0

(* Una llamada en serie: reserva, corre, libera. Todo en vuelo cabe. *)
Call(next) ==
    /\ inFlight + Reserve <= Ceiling
    /\ inFlight' = 0                 \* en serie: al terminar, nada en vuelo
    /\ state' = next

\* Lo que ninguna accion de la escalera toca salvo que lo diga.
Keep == << canonWritten, jurorsIn, jurorsDone, retcons, openS1 >>

WriteScene ==
    /\ state = "Writing"
    /\ Call("SceneGate")
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans, gatesPassed,
                    juryPassed, deltaClean, repaired, lastClosed >>
    /\ UNCHANGED Keep

ScenePasses ==
    /\ state = "SceneGate"
    /\ lastClosed' = scene
    /\ IF scene < Scenes
         THEN state' = "Writing" /\ scene' = scene + 1
         ELSE state' = "ChapterGate" /\ scene' = scene
    /\ sceneAttempts' = 0
    /\ UNCHANGED << chapterAttempts, arcReplans, gatesPassed, juryPassed,
                    deltaClean, repaired, inFlight >>
    /\ UNCHANGED Keep

SceneFailsRetry ==
    /\ state = "SceneGate"
    /\ sceneAttempts + 1 < SceneAttempts
    /\ sceneAttempts' = sceneAttempts + 1
    /\ state' = "Writing"
    /\ UNCHANGED << scene, chapterAttempts, arcReplans, gatesPassed, juryPassed,
                    deltaClean, repaired, inFlight, lastClosed >>
    /\ UNCHANGED Keep

(* Agotada la escena: reespecificar en su sitio consume un intento de capitulo. *)
SceneFailsRespec ==
    /\ state = "SceneGate"
    /\ sceneAttempts + 1 >= SceneAttempts
    /\ chapterAttempts + 1 < ChapterAttempts
    /\ sceneAttempts' = 0
    /\ chapterAttempts' = chapterAttempts + 1
    /\ state' = "Writing"
    /\ UNCHANGED << scene, arcReplans, gatesPassed, juryPassed, deltaClean,
                    repaired, inFlight, lastClosed >>
    /\ UNCHANGED Keep

SceneFailsEscalate ==
    /\ state = "SceneGate"
    /\ sceneAttempts + 1 >= SceneAttempts
    /\ chapterAttempts + 1 >= ChapterAttempts
    /\ state' = "Quarantine"
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans, gatesPassed,
                    juryPassed, deltaClean, repaired, inFlight, lastClosed >>
    /\ UNCHANGED Keep

(* Un fallo que devuelve a la reparacion consume un intento de escena. *)
ToRepair ==
    IF sceneAttempts + 1 < SceneAttempts
      THEN state' = "Repairing" /\ sceneAttempts' = sceneAttempts + 1
      ELSE state' = "Quarantine" /\ sceneAttempts' = 0

(* Continuista y examen: la puerta de capitulo. Si pasa, va al Jurado. *)
ChapterGatePasses ==
    /\ state = "ChapterGate"
    /\ gatesPassed' = TRUE
    /\ Call("Judging")
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans,
                    juryPassed, deltaClean, repaired, lastClosed >>
    /\ UNCHANGED Keep

ChapterGateFails ==
    /\ state = "ChapterGate"
    /\ gatesPassed' = FALSE
    /\ ToRepair
    /\ UNCHANGED << scene, chapterAttempts, arcReplans, juryPassed,
                    deltaClean, repaired, inFlight, lastClosed >>
    /\ UNCHANGED Keep

(* El Jurado: tres instancias en paralelo, cada una admitida solo si cabe  *)
(* con lo que ya esta en vuelo. La admision espera; nunca rebasa el techo. *)
JurorAdmitted ==
    /\ state = "Judging"
    /\ jurorsIn + jurorsDone < Jurors
    /\ inFlight + JuryReserve <= Ceiling
    /\ inFlight' = inFlight + JuryReserve
    /\ jurorsIn' = jurorsIn + 1
    /\ UNCHANGED << state, scene, sceneAttempts, chapterAttempts, arcReplans,
                    canonWritten, gatesPassed, juryPassed, openS1, deltaClean,
                    repaired, jurorsDone, retcons, lastClosed >>

JurorReturns ==
    /\ state = "Judging"
    /\ jurorsIn > 0
    /\ inFlight' = inFlight - JuryReserve
    /\ jurorsIn' = jurorsIn - 1
    /\ jurorsDone' = jurorsDone + 1
    /\ UNCHANGED << state, scene, sceneAttempts, chapterAttempts, arcReplans,
                    canonWritten, gatesPassed, juryPassed, openS1, deltaClean,
                    repaired, retcons, lastClosed >>

(* Con las tres devueltas, el veredicto. La segunda ronda de RF-130 es el *)
(* mismo abanico otra vez y no cambia el espacio de estados que importa.  *)
JuryPasses ==
    /\ state = "Judging"
    /\ jurorsDone = Jurors
    /\ juryPassed' = TRUE
    /\ jurorsDone' = 0
    /\ Call("Polishing")
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans, canonWritten,
                    gatesPassed, openS1, deltaClean, repaired, jurorsIn, retcons, lastClosed >>

(* RF-132. Una dimension bajo umbral es un defecto: vuelve a la reparacion. *)
JuryFails ==
    /\ state = "Judging"
    /\ jurorsDone = Jurors
    /\ juryPassed' = FALSE
    /\ gatesPassed' = FALSE
    /\ jurorsDone' = 0
    /\ ToRepair
    /\ UNCHANGED << scene, chapterAttempts, arcReplans, canonWritten, openS1,
                    deltaClean, repaired, inFlight, jurorsIn, retcons, lastClosed >>

(* RF-139. El Estilista pule; puede abrir un S1 que no estaba. *)
Polish ==
    /\ state = "Polishing"
    /\ openS1' \in BOOLEAN
    /\ Call("Reverifying")
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans, canonWritten,
                    gatesPassed, juryPassed, deltaClean, repaired, jurorsIn,
                    jurorsDone, retcons, lastClosed >>

(* RF-141. Reverificar: un S1 nuevo revierte el pase entero. *)
Reverify ==
    /\ state = "Reverifying"
    /\ openS1' = FALSE
    /\ Call("Extracting")
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans, canonWritten,
                    gatesPassed, juryPassed, deltaClean, repaired, jurorsIn,
                    jurorsDone, retcons, lastClosed >>

(* Toda reparacion revalida desde la primera puerta. *)
Repair ==
    /\ state = "Repairing"
    /\ repaired' = TRUE
    /\ Call("Revalidating")
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans,
                    gatesPassed, juryPassed, deltaClean, lastClosed >>
    /\ UNCHANGED Keep

Revalidate ==
    /\ state = "Revalidating"
    /\ repaired' = FALSE
    /\ state' = "ChapterGate"
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans,
                    gatesPassed, juryPassed, deltaClean, inFlight, lastClosed >>
    /\ UNCHANGED Keep

Extract ==
    /\ state = "Extracting"
    /\ Call("Arbitrating")
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans,
                    gatesPassed, juryPassed, deltaClean, repaired, lastClosed >>
    /\ UNCHANGED Keep

DeltaAccepted ==
    /\ state = "Arbitrating"
    /\ deltaClean' = TRUE
    /\ state' = "Freezing"
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans,
                    gatesPassed, juryPassed, repaired, inFlight, lastClosed >>
    /\ UNCHANGED Keep

(* RF-151. Ante un rechazo, el Arbitro puede proponer un retcon; la regla  *)
(* dura de RF-152 decide si es admisible. Acotado por los intentos.        *)
RetconProposed ==
    /\ state = "Arbitrating"
    /\ retcons < SceneAttempts
    /\ Call("Retconning")
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans, canonWritten,
                    gatesPassed, juryPassed, openS1, deltaClean, repaired,
                    jurorsIn, jurorsDone, retcons, lastClosed >>

(* RF-153, RNF-30. Recongelacion atomica: todo junto en un paso o nada. *)
RetconApplied ==
    /\ state = "Retconning"
    /\ retcons' = retcons + 1
    /\ deltaClean' = TRUE
    /\ state' = "Freezing"
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans, canonWritten,
                    gatesPassed, juryPassed, openS1, repaired, inFlight,
                    jurorsIn, jurorsDone, lastClosed >>

(* Sin propuesta o inadmisible: gana lo congelado y el rechazo es un S1. *)
RetconRefused ==
    /\ state = "Retconning"
    /\ deltaClean' = FALSE
    /\ gatesPassed' = FALSE
    /\ juryPassed' = FALSE
    /\ ToRepair
    /\ UNCHANGED << scene, chapterAttempts, arcReplans, repaired, inFlight, lastClosed >>
    /\ UNCHANGED Keep

(* Un hecho rechazado es un S1: vuelve a la reparacion, nunca al canon. *)
DeltaRejected ==
    /\ state = "Arbitrating"
    /\ deltaClean' = FALSE
    /\ gatesPassed' = FALSE
    /\ juryPassed' = FALSE
    /\ ToRepair
    /\ UNCHANGED << scene, chapterAttempts, arcReplans, repaired, inFlight, lastClosed >>
    /\ UNCHANGED Keep

Freeze ==
    /\ state = "Freezing"
    /\ gatesPassed /\ juryPassed /\ deltaClean
    /\ canonWritten' = TRUE
    /\ state' = "Frozen"
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans, gatesPassed,
                    juryPassed, openS1, deltaClean, repaired, inFlight, jurorsIn,
                    jurorsDone, retcons, lastClosed >>

(* RF-147. El Supervisor mira lo congelado; si falla, vale "sano". Replani- *)
(* ficar toca solo lo que queda por escribir, nunca lo congelado.           *)
Supervise ==
    /\ state = "Frozen"
    /\ Call("Supervised")
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans, gatesPassed,
                    juryPassed, deltaClean, repaired, lastClosed >>
    /\ UNCHANGED Keep

Reset ==
    /\ state' = "Writing" /\ scene' = 1 /\ sceneAttempts' = 0
    /\ gatesPassed' = FALSE /\ juryPassed' = FALSE /\ deltaClean' = FALSE
    /\ repaired' = FALSE /\ openS1' = FALSE
    /\ lastClosed' = 0

(* Cuarentena: reespecificar, luego replanificar, luego no hay cuarto nivel. *)
QuarantineRespec ==
    /\ state = "Quarantine"
    /\ arcReplans < ArcReplans
    /\ chapterAttempts + 1 < ChapterAttempts
    /\ chapterAttempts' = chapterAttempts + 1
    /\ Reset
    /\ UNCHANGED << arcReplans, canonWritten, inFlight, jurorsIn, jurorsDone, retcons >>

QuarantineReplan ==
    /\ state = "Quarantine"
    /\ arcReplans < ArcReplans
    /\ chapterAttempts + 1 >= ChapterAttempts
    /\ arcReplans' = arcReplans + 1
    /\ chapterAttempts' = 0
    /\ Reset
    /\ UNCHANGED << canonWritten, inFlight, jurorsIn, jurorsDone, retcons >>

QuarantineAbort ==
    /\ state = "Quarantine"
    /\ arcReplans >= ArcReplans
    /\ state' = "Aborted"
    /\ UNCHANGED << scene, sceneAttempts, chapterAttempts, arcReplans, gatesPassed,
                    juryPassed, deltaClean, repaired, inFlight, lastClosed >>
    /\ UNCHANGED Keep

Done ==
    /\ state \in { "Supervised", "Aborted" }
    /\ UNCHANGED vars

Next ==
    \/ WriteScene \/ ScenePasses \/ SceneFailsRetry \/ SceneFailsRespec \/ SceneFailsEscalate
    \/ ChapterGatePasses \/ ChapterGateFails
    \/ JurorAdmitted \/ JurorReturns \/ JuryPasses \/ JuryFails
    \/ Polish \/ Reverify \/ Repair \/ Revalidate
    \/ Extract \/ DeltaAccepted \/ DeltaRejected
    \/ RetconProposed \/ RetconApplied \/ RetconRefused
    \/ Freeze \/ Supervise
    \/ QuarantineRespec \/ QuarantineReplan \/ QuarantineAbort
    \/ Done

Spec == Init /\ [][Next]_vars /\ WF_vars(Next)

(* ----------------------------------------------------------------------- *)
(* Los seis invariantes de verification.md §5.10, sobre el flujo entero      *)

TypeOK == state \in States /\ inFlight \in 0..Ceiling /\ jurorsIn + jurorsDone <= Jurors

\* Nunca se congela sin superar todas las puertas, el Jurado incluido.
NeverFreezeWithoutGates ==
    (state \in { "Frozen", "Supervised" }) => (gatesPassed /\ juryPassed /\ deltaClean)

\* Nunca se escribe canon antes de congelar.
NoCanonBeforeFreeze == canonWritten => (state \in { "Frozen", "Supervised" })

\* Toda reparacion revalida desde la primera puerta, y ningun S1 abierto por
\* el pase de estilo llega a la extraccion sin revertirse (RF-141).
RepairRevalidates ==
    /\ (state \in { "Judging", "Polishing", "Extracting", "Arbitrating", "Retconning",
                    "Freezing", "Frozen", "Supervised" }) => ~repaired
    /\ (state \in { "Extracting", "Arbitrating", "Retconning", "Freezing", "Frozen",
                    "Supervised" }) => ~openS1

\* Nunca hay mas de CTX-20 tokens en vuelo, tampoco con el Jurado en paralelo.
CtxI1 == inFlight <= Ceiling

\* Nunca se reanuda desde un punto que no este cerrado.
ResumeOnlyClosed == lastClosed <= scene

\* La escalera esta acotada, y el retcon tambien.
LadderBounded ==
    /\ arcReplans <= ArcReplans /\ chapterAttempts <= ChapterAttempts
    /\ sceneAttempts <= SceneAttempts /\ retcons <= SceneAttempts

\* Y termina: toda ejecucion acaba supervisada o abortada.
Terminates == <>(state \in { "Supervised", "Aborted" })

=============================================================================
