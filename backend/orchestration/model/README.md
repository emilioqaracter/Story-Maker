# Modelo TLA+ del Orquestador · VER-18

Este es el modelo formal de lo que hace `orchestration/` durante una tirada. Lo comprueba TLC, y es el método VER-18 de `docs/verification.md` §5.10. **Prueba el flujo modelado, no el código que lo implementa.** La distancia entre los dos la cubre VER-05, con los tests que cita la tabla de §4, y las diferencias conocidas están en §6.

| Fichero | Qué es |
|---|---|
| `chapter.tla`, `chapter.cfg` | El ciclo de vida de **un** capítulo: escenas en serie, puerta de capítulo, Jurado en paralelo con admisión, pase de estilo, extracción, arbitraje con retcon, congelación, supervisión y escalera de cuarentena |
| `run.tla`, `run.cfg` | La **tirada completa**: configuración → planificación → N capítulos → cierre de obra, con caída y reanudación desde el punto de reanudación, y enmiendas del lector que publican la versión N+1. Reutiliza `chapter.tla` con `INSTANCE` |
| `run_reach.cfg` | Comprobación de alcance: TLC tiene que llegar a `Published` |
| `code-today/*.cfg` | El código **anterior al commit `91a1457`**, que arregló los cuatro fallos. Cada fichero apaga una de las cuatro correcciones de §7.1 y conserva el contraejemplo de su fallo; su cabecera dice que el código ya no la necesita y qué test lo prueba. `b4_budget_liveness.cfg` comprueba que, aun con ese fallo, la tirada terminaba |
| `mutations/*.tla` | Copias de `run.tla` con un solo cambio, marcado `MUTACION`, que rompe a propósito un invariante o la liveness |
| `run_tlc.sh` | Lo ejecuta todo, guarda cada salida en `tlc/` con su cabecera y falla si algo no da lo esperado |
| `tlc/*.txt` | Las salidas completas de TLC: estados generados, estados distintos, profundidad y trazas |

## 1. Qué modela y qué no

**Modela:**

- La configuración: el brief válido crea la novela y el inválido no.
- La planificación con su reintento.
- El bucle de capítulos con la guarda RF-107.
- El capítulo entero, tomado de `chapter.tla`.
- El delta vacío que aborta.
- Los abortos de la escalera y de la replanificación tras congelar.
- El cierre de obra, con y sin sus condiciones.
- La caída en cualquier fase de la tirada.
- La reanudación tal como la hace `run`.
- Las enmiendas del lector: en cola, aplicadas o rechazadas, y solo entre congelaciones o sin tirada en marcha.
- Las versiones del manuscrito, con lo que muestra cada una.

**No modela:**

- El contenido de la prosa ni de la escaleta. Un texto es un número de revisión con una marca que dice si pasó sus puertas.
- La segunda ronda del Jurado (RF-130).
- La deriva de estilo.
- El conjunto dorado.
- Qué replanifica el Supervisor. Solo se modela que su replanificación puede abortar.

## 2. Cómo ejecutar TLC en Windows

Hace falta Java 11 o superior y `tla2tools.jar`. En la máquina de la entrega están en:

- java: `C:\Program Files\Eclipse Adoptium\jdk-21.0.12.101-hotspot\bin\java.exe` (Temurin 21)
- TLC: `C:\tools\tla\tla2tools.jar` (TLC 2.19, del 08-08-2024)

Si no están, se instalan desde PowerShell:

```powershell
winget install --id EclipseAdoptium.Temurin.21.JDK -e
New-Item -ItemType Directory -Force C:\tools\tla
curl.exe -L -o C:\tools\tla\tla2tools.jar https://github.com/tlaplus/tlaplus/releases/latest/download/tla2tools.jar
```

Comprueba con `java -cp C:\tools\tla\tla2tools.jar tlc2.TLC -h` qué versión imprime. Las salidas de `tlc/` son de la 2.19; con otra, los números de estados deberían coincidir y las trazas podrían ser otras de la misma longitud.

Todo de una vez, desde Git Bash. Tarda unos dos minutos y medio:

```bash
cd backend/orchestration/model
bash run_tlc.sh            # todo; sale con 0 solo si las 13 comprobaciones dan lo esperado
bash run_tlc.sh run        # solo lo que empieza por "run"
JAVA=/ruta/java TLA2TOOLS_JAR=/ruta/tla2tools.jar bash run_tlc.sh   # con otras rutas
```

Un modelo suelto:

```bash
JAVA="/c/Program Files/Eclipse Adoptium/jdk-21.0.12.101-hotspot/bin/java.exe"
cd backend/orchestration/model
"$JAVA" -XX:+UseParallelGC -cp C:/tools/tla/tla2tools.jar tlc2.TLC -config run.cfg -workers auto -metadir "$TEMP/tlc" run.tla
# una mutacion: se ejecuta desde mutations/ y necesita encontrar chapter.tla
cd mutations && "$JAVA" -DTLA-Library="$(cd .. && pwd -W)" -cp C:/tools/tla/tla2tools.jar tlc2.TLC -config m1_freeze_sin_puerta.cfg m1_freeze_sin_puerta.tla
```

`-metadir` fuera del repo evita dejar `states/` en el árbol. La comprobación de sintaxis sola se hace con `"$JAVA" -cp C:/tools/tla/tla2tools.jar tla2sany.SANY run.tla`.

## 3. Resultados

Salidas en `tlc/`. El commit y la fecha de cada una están en su cabecera.

| Ejecución | Resultado | Generados | Distintos | Profundidad | Tiempo |
|---|---|---|---|---|---|
| `chapter` | No error has been found | 2.636 | 1.831 | 152 | 1 s |
| `run`, 5 capítulos | **No error has been found**, con las dos propiedades temporales comprobadas sobre el espacio completo | 1.021.146 | **508.470** | 242 | 51 s |
| `run_reach` | `NeverPublished` violado: `Published` es alcanzable | 136.682 | 70.990 | 109 | 2 s |

Con varios workers, la profundidad puede variar en ±1 entre ejecuciones, y un contraejemplo puede salir por otra traza de longitud parecida. Los estados distintos no varían. Por eso §7 describe las trazas por sus pasos y no por su longitud: la guardada en `tlc/` es la que vale.

**El modelo pequeño de `run.cfg`** es este:

- `Chapters = 5`.
- `Scenes = 2`.
- `SceneAttempts = 3`, es decir, dos reintentos.
- `ChapterAttempts = 2` y `ArcReplans = 1`. Con los dos anteriores son los números de RF-18 y de `retries.py`.
- `PlanAttempts = 2`. Sale de `_plan_with_gate`, que aborta con `arc_replans > ARC_REPLANS` desde `91a1457`; antes era el literal `> 2`, y el modelo tenía 3.
- `MaxCrashes = 1` y `MaxAmends = 1`.
- Los tokens (`Ceiling`, `Reserve`, `JuryReserve`, `Jurors`) son los de `chapter.cfg`: CTX-20 y D-37.

`Chapters`, `MaxCrashes` y `MaxAmends` son **números de modelo**, no del código. Acotan el espacio de estados.

**Reducción del espacio de estados.** La primera versión de `run.tla` crecía unas 26 veces por capítulo: 163.336 estados distintos con 2 capítulos y 4.281.495 con 3. Con 5 no terminó en diez minutos y se paró. La causa eran los retcons que reescriben capítulos ya congelados. Tres cambios lo arreglaron, sin perder nada que un invariante mire:

1. **La reescritura conserva la marca de puertas del capítulo.** Un retcon reverifica los pasajes que toca, no aprueba los que no toca.
2. **Con la versión 1 vigente no se explora el retcon sobre capítulos congelados.** No hay ninguna versión anterior que pueda alterar, y la marca no cambia.
3. **Una segunda reescritura del mismo capítulo dentro de la misma versión tampoco se explora.** Deja todas las vistas igual que la primera (variable `touched`).

Con eso, 5 capítulos son 508.470 estados (510.546 con `PlanAttempts = 3`).

## 4. Acción TLA+ ↔ código

Se cita por `fichero:función` para que la tabla sobreviva a los cambios de línea. Las rutas son relativas a `backend/`.

### 4.1 `run.tla`

| Acción | Código | Test VER-05 del mismo camino |
|---|---|---|
| `Configure`, `ConfigRejected` | `canon/brief.py:create_novel` y su validación del brief | `canon/test_brief.py::test_crear_la_novela_deja_el_canon_consultable`, `::test_una_relacion_a_una_entidad_inexistente_se_rechaza` |
| `PlanFails`, `PlanAborts`, `PlanPasses` | `orchestration/loop.py:_plan_with_gate` (`outline.check`, `on_failure(Level.ARC)`, `RunAbortedError` con `arc_replans > ARC_REPLANS`); `PlanPasses` también es el arranque de `_run_chapters`: `load_outline` o `_plan_with_gate` y `save_outline`, `load(path) or ResumePoint(chapter=1)`, `may_start_chapter`, `_chapter_frozen` para saltar el capítulo ya congelado (B1) y `Budget(chapter_attempts=…, arc_replans=…)` del punto (B4) | `orchestration/test_loop.py::test_una_escaleta_que_no_pasa_no_arranca`, `::test_la_escaleta_rechazada_vuelve_con_sus_defectos` |
| `ChapterStep` | Las acciones de `chapter.tla` que no tocan nada persistente (§4.2) | Los de §4.2 |
| `ScenePasses` | `loop.py:_write_chapter`: `drafts.save_draft` y `checkpoint.save` con el presupuesto, que borra los borradores posteriores (`orchestration/checkpoint.py:save`) | `orchestration/test_checkpoint.py::test_guardar_descarta_los_borradores_posteriores`, `test_loop.py::test_el_punto_de_reanudacion_avanza` |
| `SceneFailsEscalate` | `loop.py:_write_scene` devuelve la escena bloqueante, tras guardar el intento de capítulo gastado con `checkpoint.save_budget`; `_write_chapter` ya no guarda su borrador ni avanza el punto (`cerrado_hasta_aqui`, B3) | `test_loop.py::test_agotada_la_escalera_el_capitulo_se_rehace_y_luego_se_replanifica`, `test_checkpoint.py::test_b3_una_escena_que_no_paso_su_puerta_no_se_reutiliza` |
| `ExtractEmpty` | `loop.py:_extract_with_retries` → `EmptyDeltaError` | `test_loop.py::test_un_archivero_que_no_extrae_nada_no_congela` |
| `RetconApplied`, `RetconPartial` | `loop.py:_extract_and_validate` y `_try_retcon` → `canon/arbiter/refreeze.py:commit`, que guarda la historia con `_keep_history` (B2) | `test_loop.py::test_un_retcon_admisible_se_aplica_y_el_capitulo_congela_limpio`, `::test_b2_un_retcon_con_la_version_2_creada_no_cambia_la_1` |
| `Freeze` | `loop.py:_freeze` → `canon/freeze/freeze.py:commit_chapter`, con `purge_working_memory` | `test_loop.py::test_la_purga_deja_la_memoria_de_trabajo_vacia`, `::test_lo_congelado_queda_consultable` |
| `PostFreezeAborts` | `loop.py:_close_act_if_needed` y `_supervise` → `_replan`, que lanza `RunAbortedError` | `test_loop.py::test_una_deriva_replanifica_solo_lo_que_queda` |
| `QuarantineAbort` | `loop.py:_write_chapter`, `case _` → `RunAbortedError` | `test_loop.py::test_agotada_la_escalera_el_capitulo_se_rehace_y_luego_se_replanifica` |
| `SaveNext` | `loop.py:_run_chapters`: `save_outline` y `save(path, ResumePoint(chapter=numero + 1))` | `test_checkpoint.py::test_el_punto_sobrevive_a_la_congelacion`, `::test_b1_una_caida_tras_congelar_no_recongela_el_capitulo` |
| `StartChapter` | `loop.py:run`: la vuelta del `for`, con `may_start_chapter` (`orchestration/retries.py`) | `test_loop.py::test_cada_capitulo_empieza_con_su_escalera_entera` |
| `ToClose`, `WorkCloses`, `WorkNotClosed` | `loop.py:_work_closes` y `trace.emit("work.close")` | `test_loop.py::test_una_tirada_completa_cierra_sola`, `::test_la_obra_no_cierra_con_promesas_sin_cobrar`, `::test_la_obra_no_cierra_fuera_de_rango` |
| `Crash` | El proceso muere. Sobrevive lo que está en el fichero: `wm_run_state` (con reintentos consumidos y escaleta vigente desde la migración 6), `wm_draft`, canon, versiones y `change_request`, y una solicitud en `applying` vuelve a `queued` (`canon/manuscript.py:next_queued`) | `test_loop.py::test_reanudar_da_el_mismo_manuscrito_que_no_interrumpir`, `test_checkpoint.py::test_una_caida_pierde_como_mucho_una_escena` |
| `Resume` | Relanzar `loop.py:run`, que lee la escaleta con `orchestration/checkpoint.py:load_outline` y el punto con `load` | `test_loop.py::test_reanudar_da_el_mismo_manuscrito_que_no_interrumpir`, `test_checkpoint.py::test_r1_reanudar_sigue_con_la_escaleta_vigente` |
| `AmendRequested` | `orchestration/amend.py:create_request` (RI-47) | `orchestration/test_amend.py::test_una_peticion_interpretable_queda_en_cola_con_su_interpretacion` |
| `AmendApplied` | `amend.py:apply_pending` → `_apply` → `canon/manuscript.py:commit_amendment`, llamado desde `after_freeze` en `loop.py:run` o desde `orchestration/compose.py:amend_novel` → `amend.py:drain` | `test_amend.py::test_aplicar_un_cambio_de_nombre_crea_la_version_2_y_conserva_la_1`, `::test_el_bucle_llama_a_las_enmiendas_tras_cada_congelacion` |
| `AmendRejected` | `amend.py:_apply` lanza `RejectedError` → `amend.py:_reject` | `test_amend.py::test_un_s1_que_no_es_la_enmienda_la_rechaza_sin_tocar_nada`, `::test_si_el_reparador_deja_el_valor_anterior_se_rechaza` |
| `Done` | La tirada acabó y no queda nada en cola | — |

### 4.2 `chapter.tla`

| Acción | Código | Test VER-05 |
|---|---|---|
| `WriteScene` | `loop.py:_write_scene` → `engine.write_scene` o `simulate_match` más `narrate_match` | `test_loop.py::test_una_escena_de_encuentro_se_resuelve_antes_de_narrarse` |
| `ScenePasses` | `loop.py:_write_scene`, `if not resultado.blocking` | `test_loop.py::test_una_escena_con_defecto_grave_se_reintenta` |
| `SceneFailsRetry` | `loop.py:_write_scene` con `retries.py:on_failure` → `Action.RETRY` | `test_loop.py::test_el_reintento_lleva_el_defecto_del_intento_anterior` |
| `SceneFailsRespec` | `loop.py:_write_scene` → `engine.respec`; `on_failure` → `QUARANTINE_AND_RESPEC` | `test_loop.py::test_agotada_la_escalera_el_capitulo_se_rehace_y_luego_se_replanifica` |
| `SceneFailsEscalate` | `loop.py:_write_scene`, `presupuesto.chapter_attempts >= CHAPTER_ATTEMPTS`, y después `_approve_chapter` devuelve `None` | el mismo |
| `ChapterGatePasses`, `ChapterGateFails` | `loop.py:_approve_chapter`: `review_chapter`, examen, `verification/gates.py:chapter_gate` | `test_loop.py::test_un_defecto_del_continuista_se_repara_y_el_capitulo_congela`, `::test_tres_respuestas_erroneas_del_examen_no_pasan_la_puerta` |
| `ToRepair`, `Repair`, `Revalidate` | `loop.py:_repair_pass` y el `while True` de `_approve_chapter`, que vuelve a la puerta de capítulo | `test_loop.py::test_una_reparacion_que_abre_un_s1_se_revierte` |
| `JurorAdmitted`, `JurorReturns` | `orchestration/engine.py` `judge_chapter` (`ThreadPoolExecutor`) con `orchestration/admission.py` `admit` y `release` | `orchestration/test_admission.py::test_lo_en_vuelo_nunca_supera_el_techo`, `::test_lo_que_no_cabe_se_encola` |
| `JuryPasses`, `JuryFails` | `loop.py:_approve_chapter`, `jurado.passed` | `test_loop.py::test_un_jurado_bajo_umbral_manda_a_reparar_y_vuelve_a_juzgar` |
| `Polish`, `Reverify` | `loop.py:_polish` y `_new_s1_after` | `test_loop.py::test_un_pase_de_estilo_que_abre_un_s1_se_revierte` |
| `Extract` | `loop.py:_extract_and_validate` → `_extract_with_retries` | `test_loop.py::test_congelar_hace_evolucionar_el_canon` |
| `DeltaAccepted`, `DeltaRejected` | `loop.py:_approve_chapter`: `validacion.clean`, o `rejections` a defectos | `test_loop.py::test_un_hecho_que_reescribe_el_pasado_se_arbitra_y_se_repara` |
| `RetconProposed`, `RetconApplied`, `RetconPartial`, `RetconRefused` | `loop.py:_try_retcon` (`retcon_rules.plan`, `engine.propose_retcon`, `retcon_rewrite`) y la lista `restantes` de `_extract_and_validate` | `test_loop.py::test_un_retcon_admisible_se_aplica_y_el_capitulo_congela_limpio`, `::test_sin_propuesta_gana_el_canon_como_en_la_version_1` |
| `Freeze` | `loop.py:_freeze` → `commit_chapter` | `test_loop.py::test_la_congelacion_guarda_veredictos_y_huella` |
| `Supervise` | `loop.py:_supervise` | `test_loop.py::test_un_supervisor_que_falla_cuenta_como_sano_y_consta` |
| `QuarantineRespec`, `QuarantineReplan`, `QuarantineAbort` | `loop.py:_write_chapter`, el `match decision.action`, con `retries.py:on_failure` en los niveles `CHAPTER` y `ARC` | `test_loop.py::test_agotada_la_escalera_el_capitulo_se_rehace_y_luego_se_replanifica` |

## 5. Invariantes y propiedades

Todos están en `run.cfg`, y todos pasan en el modelo con las cuatro correcciones de §7.1 activas, que son el código desde `91a1457`. Con el código anterior fallaban los que marca §7.1.

| Nombre | Qué dice, en castellano | Qué lo rompe |
|---|---|---|
| `NeverPublishUngated` | Ninguna versión del manuscrito, ni la vigente ni las anteriores, muestra un capítulo cuyo texto no pasó todas sus puertas. Son cuatro: la de escena, la de capitulo (Continuista y examen), el Jurado y el arbitraje del delta | B3; M1 |
| `NoChapterDuplicated` | La reanudación no duplica: ningún capítulo se congela dos veces | B1 |
| `NoChapterLost` | La reanudación no pierde: mientras se escribe el capítulo N, del 1 al N−1 están congelados, y al cerrar lo están todos | Ninguna mutación lo rompe. Lo sostiene la guarda RF-107 de `PlanPasses` y `StartChapter` |
| `ResumeOnlyClosed` | PRO-I2. El punto de reanudación solo cubre escenas cerradas que pasaron su puerta, y no queda ningún borrador posterior a él. Es exactamente lo que `Resume` reutiliza. Sustituye al de `chapter.tla`, que se cumplía por construcción | B3; M4 |
| `PreviousVersionPreserved` | La versión anterior se conserva tras una regeneración: lo que mostraba cada versión cuando dejó de ser la vigente es lo que sigue mostrando después | B2; M3 |
| `RetriesWithinLimit` | Los reintentos nunca superan el límite, tampoco sumando caídas: la escalera de RF-18, la planificación (menos de `PlanAttempts`), los retcons (`RetconsBounded`) y los intentos de capítulo y de tramo gastados en un mismo capítulo aunque haya caídas por medio | B4 |
| `ChapterSafety` | Dentro de la tirada siguen valiendo los de `chapter.tla`: `NeverFreezeWithoutGates`, `NoCanonBeforeFreeze`, `RepairRevalidates` y `CtxI1` | — |
| `TypeOK` | Los tipos | — |

**`RetconsBounded`**, que está en `chapter.tla` y dentro de `RetriesWithinLimit`: los retcons de un capítulo son como mucho `SceneAttempts × (ChapterAttempts + ArcReplans)`, es decir, 9. **No viene de ninguna guarda**: el modelo, como el código, no cuenta retcons. Sale de la escalera, porque todo pase que llega al Árbitro y no congela consume un intento de escena.

**Liveness:**

- `GenerationTerminates == <>(phase \in {"Published", "Unclosed", "Aborted"})`: toda generación termina publicando, o con error. `Unclosed` es el cierre con `closed=False`; `Aborted`, un `RunAbortedError`, un `EmptyDeltaError` o un brief rechazado.
- `AmendmentsSettle == [](queue > 0 => <>(queue = 0))`: toda solicitud en cola acaba aplicada o rechazada.

**Equidad.** `Spec == Init /\ [][Next]_vars /\ WF_vars(Progress)`.

- **`Progress` es `Next` sin `Crash`, sin `AmendRequested` y sin `Done`.** Crash y AmendRequested vienen de fuera del sistema y pueden no ocurrir nunca. Pedirles equidad obligaría al modelo a caerse o a recibir solicitudes. Done es un tartamudeo.
- **Las caídas están acotadas por `MaxCrashes`.** Sin ese tope la tirada podría caerse y reanudarse para siempre, y M2 lo demuestra.
- **Basta la equidad débil.** Ninguna acción de `Progress` se desactiva y reactiva sin fin: cada una consume un contador acotado (`sceneAttempts`, `chapterAttempts`, `arcReplans`, `planTries`, `queue`) o avanza de fase, y en todo estado no terminal hay alguna habilitada.

## 6. Diferencias entre el modelo y el código

| Diferencia | Por qué | Riesgo |
|---|---|---|
| **Tope de retcons.** `chapter.tla` tenía `retcons < SceneAttempts` y el código no tiene contador. Se quitó la guarda, se añadió `RetconPartial` y `RetconsBounded` prueba la cota que da la escalera | Cuadrar el modelo con el código | El modelo cuenta pases con al menos un retcon. El código puede aplicar varios en un pase, uno por hecho rechazado, así que su cota es 9 × (hechos rechazados por pase) |
| **Reescrituras por capítulo, de ninguno o de uno.** En el código son escenas, hasta tres pasajes | Tamaño del modelo | Un retcon o una enmienda que toque dos capítulos no se explora. Los fallos de §7.1 ya salen con uno |
| **La reanudación no modela la escaleta.** Desde `91a1457`, `run` reanuda con la escaleta guardada en `wm_run_state` y solo llama a `_plan_with_gate` si no hay ninguna. En el modelo, `Resume` sigue pasando por `Planning`, con `PlanFails` y `PlanAborts` | El modelo no tiene el contenido de la escaleta | Ninguno para los invariantes: el modelo explora más caminos que el código, no menos. R1 de §7.1 lo prueba en Python |
| `PlanAttempts = 2` sale de `retries.ARC_REPLANS` en `_plan_with_gate`, desde `91a1457` | Es lo que hace el código | Ninguno. Antes era el literal `> 2`, un número fuera de RF-18 |
| **La cuarentena devuelve el punto al principio del capítulo.** Desde `91a1457`, `_write_chapter` guarda `ResumePoint(chapter=N)` con el presupuesto al decidir la cuarentena, y eso borra los borradores del capítulo. En el modelo, `QuarantineRespec` y `QuarantineReplan` no tocan `drafts` ni `ckScene` | D-26: la cuarentena rehace el capítulo entero, y reanudar tiene que dar lo mismo que no caer (RNF-08) | Ninguno: el modelo reutiliza más de lo que el código reutiliza, y `ResumeOnlyClosed` pasa igual. Lo que no se guarda es la especificación reescrita por `respec`: tras una caída se rehace con la de `specs_for` |
| `EmptyDeltaError` es una excepción sin capturar, no un `RunAbortedError`. En el modelo es `Aborted` | Termina la tirada con error | Relanzar la tirada lo reanudaría. El modelo no lo explora |
| La caída entre `drafts.save_draft` y `checkpoint.save` no se modela: las dos van en un solo paso | Tamaño del modelo | Deja un borrador posterior al punto que `load_drafts` reutilizaría. Lo cubre en parte M4, que muestra que `ResumeOnlyClosed` lo detecta |
| El Supervisor y la puerta de acto son un solo `PostFreezeAborts` antes de `Supervise` | El modelo no tiene su contenido | Ninguno para los invariantes: los dos caen en la misma ventana de caída |
| La segunda ronda del Jurado (RF-130) no está | Es el mismo abanico otra vez | Ninguno, ver `chapter.tla` |

## 7. Contraejemplos

### 7.1 Fallos que encontró TLC en el código, y su arreglo

Salieron **al modelar el código**: el modelo fiel al código no podía cumplir el invariante. TLC los confirma con los `.cfg` de `code-today/`. Cada corrección es una bandera de `run.tla`: `run.cfg` las pone a `TRUE`, y el código anterior al arreglo es la bandera a `FALSE`.

**Los cuatro, y R1, están arreglados en el commit `91a1457`.** Para cada uno, el camino es contraejemplo → test → commit:

| Fallo | Contraejemplo de TLC | Test que lo reproduce con dobles deterministas y falla con el código anterior | Arreglo, en `91a1457` |
|---|---|---|---|
| B1 | `tlc/code-today_b1_double_freeze.txt` | `orchestration/test_checkpoint.py::test_b1_una_caida_tras_congelar_no_recongela_el_capitulo` | `orchestration/loop.py:_run_chapters`: un capítulo con prosa congelada no se reescribe, sigue desde su puerta de acto |
| B2 | `tlc/code-today_b2_retcon_history.txt` | `orchestration/test_loop.py::test_b2_un_retcon_con_la_version_2_creada_no_cambia_la_1`; unitarios en `canon/arbiter/test_retcon.py` | `canon/arbiter/refreeze.py:commit` → `_keep_history`: toda recongelación guarda lo que ven las versiones no vigentes (RD-34, PRO-08) |
| B3 | `tlc/code-today_b3_checkpoint.txt`, `tlc/code-today_b3_blocked_scene_frozen.txt` | `orchestration/test_checkpoint.py::test_b3_una_escena_que_no_paso_su_puerta_no_se_reutiliza` | `orchestration/loop.py:_write_chapter`: el punto y el borrador solo avanzan mientras todas las escenas del pase pasaron su puerta (PRO-I2); la cuarentena devuelve el punto al principio del capítulo |
| B4 | `tlc/code-today_b4_budget.txt` | `orchestration/test_checkpoint.py::test_b4_reanudar_conserva_los_reintentos_consumidos` | `orchestration/checkpoint.py` (`ResumePoint.chapter_attempts`, `arc_replans`, `save_budget`), `loop.py:_write_scene` (`on_budget`), `_write_chapter` y `_run_chapters`; migración 6 de `canon/db/migrations.py` |
| R1 | Sin contraejemplo formal (§6) | `orchestration/test_checkpoint.py::test_r1_reanudar_sigue_con_la_escaleta_vigente` | `orchestration/checkpoint.py` (`save_outline`, `load_outline`), `loop.py:_run_chapters` y `_write_chapter`; migración 6 |

Tras el arreglo, `run_tlc.sh` se volvió a ejecutar: `run.cfg` sigue sin error y cada `code-today/*.cfg` sigue dando su contraejemplo, que ahora documenta el código anterior. Las salidas de `tlc/` llevan el commit en su cabecera.

**B1 · Una caída tras congelar recongela el capítulo.** Falla `NoChapterDuplicated`. Salida: `tlc/code-today_b1_double_freeze.txt`.

- *Traza*: el capítulo 1 congela (`Freeze`), luego `Crash` antes de `SaveNext`, luego `Resume` y `PlanPasses`. Se reescribe el capítulo 1 entero, con `Freeze` otra vez y `freezes[1] = 2`.
- *En el código anterior al arreglo*: entre `commit_chapter`, dentro de `loop.py:_write_chapter`, y `save(path, ResumePoint(chapter=numero + 1))`, en `loop.py:run`, corren la puerta de acto, el Supervisor y el conjunto dorado, todos con llamadas a modelo. El punto se queda en `(N, última escena)`, y la congelación ya purgó los borradores. Al reanudar, `run` vuelve a entrar en el capítulo N, no encuentra borradores y lo escribe de nuevo. `write_index` hace `INSERT OR REPLACE`, así que la prosa congelada se sustituye y el delta entra otra vez en `event`.
- *Reproducción en Python, antes del arreglo*: una caída simulada (`BaseException`) en `supervise` del capítulo 1. Resultado: `chapter.frozen` aparece para `[1, 1, 2]`, las escenas escritas son `c1e1, c1e2, c1e1, c1e2, c2e1, c2e2` y los eventos del capítulo 1 pasan de 1 a 2.
- *Arreglo* (`ResumeSkipsFrozen`, `91a1457`): en `_run_chapters`, un capítulo con prosa ya congelada (`_chapter_frozen(path, numero)`) no se reescribe; se traza `chapter.resumed` y se sigue desde su puerta de acto. Se descartó escribir el punto N+1 en la misma transacción que `commit_chapter`, porque se saltaría la puerta de acto y el Supervisor de N.
- *Test*: `test_b1_…`. Con el código anterior, `chapter.frozen` sale para `[1, 1, 2]`; con el arreglo, `[1, 2]`, las escenas escritas son `c1e1, c1e2, c2e1, c2e2` y el capítulo 1 tiene un solo evento en `event`.

**B2 · Un retcon del Árbitro cambia una versión ya publicada.** Falla `PreviousVersionPreserved`. Salida: `tlc/code-today_b2_retcon_history.txt`.

- *Traza*: el capítulo 1 congela y `AmendApplied` crea la versión 2. En el capítulo 2, `RetconApplied` reescribe una escena del 1 que la enmienda no tocó. Al final, `hist[1] = {}` y la vista de la versión 1 del capítulo 1 pasa de la revisión 1 a la 2.
- *En el código anterior al arreglo*: `loop.py:_try_retcon` llama a `refreeze.commit`, que no escribe `scene_text_history`. `canon/manuscript.py:text_at` devuelve el texto vigente para toda escena sin historial, así que la versión 1 muestra el texto nuevo sin que exista una versión nueva. Solo `commit_amendment` guarda historial.
- *Reproducción en Python, antes del arreglo*: sobre la fixture de `test_amend.py`, `apply_pending` crea la versión 2 y después un `refreeze.commit` como el de `_try_retcon` actúa sobre `c1e2`. `_textos(novela, 1)` pasa de `[…, "Lucía miró las nubes sola.", …]` a `[…, "Lucía miró las nubes acompanada.", …]`.
- *Arreglo* (`RetconKeepsHistory`, `91a1457`): en `refreeze.commit`, y no en `_try_retcon`, para que valga para **toda** recongelación. Con la versión `v > 1` vigente, antes de reemplazar una escena de un capítulo que ya estaba en la `v − 1`, guarda su texto con `until_version = v − 1` si ninguna fila llega a `v − 1`. En una enmienda es un no-op: `commit_amendment` ya guardó la fila de la versión que deja de ser vigente.
- *Test*: `test_b2_…`, sobre el bucle entero: el capítulo 1 congela, `after_freeze` crea la versión 2 sin tocar escenas, y el retcon del capítulo 2 reescribe `c1e1` y `c1e2`. Con el código anterior la versión 1 muestra `v2`; con el arreglo, `v1`, y la 2 marca las dos escenas como cambiadas.

**B3 · Una escena que agotó su escalera sin pasar su puerta entra en el canon tras una caída.** Falla `ResumeOnlyClosed` y, como consecuencia, `NeverPublishUngated`. Salidas: `tlc/code-today_b3_checkpoint.txt` y `tlc/code-today_b3_blocked_scene_frozen.txt`.

- *Traza*:
  1. Una escena agota sus intentos, se reespecifica y los vuelve a agotar: `SceneFailsEscalate`. El punto la cubre (`ckScene`) con un borrador `"bad"`.
  2. `Crash`, antes de que la cuarentena rehaga la primera escena.
  3. `Resume`. Se reutilizan las escenas del punto, esa incluida, con `scenesOk = FALSE`.
  4. El capítulo pasa su puerta, el Jurado y el arbitraje, y congela: `revs[1] = <<FALSE>>`.
- *En el código anterior al arreglo*: `_write_scene` devuelve la escena bloqueante cuando se agota la escalera, y `_write_chapter` guarda igualmente su borrador y `ResumePoint(last_closed_scene=ordinal)`. Tras la caída, la cuarentena (`respec`, `_replan`) no ha llegado a escribir nada, así que `run` reutiliza el borrador como escena cerrada, con `SceneResult(defects=[])`, y ya no vuelve a pasar por la puerta de escena.
- *Reproducción en Python, antes del arreglo*: con `verify_scene` que siempre da un S1 en `c1e2` y una caída dentro de `replan_act`, la traza tiene `scene.resumed` para `(1, 1)` y `(1, 2)`, y `chapter.frozen` para `[1, 2]`. El capítulo 1 congela con una escena que nunca pasó su puerta. `_new_s1_after` vuelve a ver el S1, pero solo revierte el pase de estilo.
- *Arreglo* (`CheckpointOnlyPassed`, `91a1457`): `_write_chapter` no guarda borrador ni punto de una escena bloqueante, ni de las que la siguen en el mismo pase: el punto cubre un prefijo de escenas cerradas. Además, al decidir la cuarentena el punto vuelve al principio del capítulo (§6).
- *Test*: `test_b3_…`, con la misma caída dentro de `replan_act`. Con el código anterior el punto queda en `(1, 2)` y la segunda tirada congela el capítulo 1; con el arreglo el punto no cubre `c1e2`, la segunda tirada la reescribe, no pasa, y aborta sin congelar.

**B4 · La reanudación reinicia la escalera.** Falla `RetriesWithinLimit`. Salida: `tlc/code-today_b4_budget.txt`.

- *Traza*: una escena agota sus intentos y se reespecifica, lo que gasta un intento de capítulo. Luego `Crash` y `Resume` con `chapterAttempts = 0`, y el capítulo vuelve a reespecificarse: `spentCh = 2` con `ChapterAttempts = 2`.
- *En el código anterior al arreglo*: `run` crea `Budget()` nuevo para cada `_write_chapter`, y el punto de reanudación no guarda el presupuesto. `docs/architecture.md` §7.4 dice que al reanudar se conservan «las escenas ya cerradas del capítulo y su cuenta de reintentos consumidos». **Era una contradicción entre código y arquitectura.** Con caídas acotadas la tirada termina igual: `GenerationTerminates` y `AmendmentsSettle` pasan también con la bandera a `FALSE` (`tlc/code-today_b4_budget_liveness.txt`, 920.140 estados distintos con `PlanAttempts = 2`). Pero cada caída regalaba una escalera entera.
- *Arreglo* (`ResumeKeepsBudget`, `91a1457`): gana `architecture.md` §7.4. `wm_run_state` gana `chapter_attempts` y `arc_replans` (migración 6). Se guardan en cuanto cambian: en `_write_scene` al gastar un intento de capítulo (`on_budget` → `checkpoint.save_budget`), en la decisión de cuarentena y con cada escena cerrada. `_run_chapters` los restaura para el capítulo del punto.
- *Test*: `test_b4_…`, con la caída dentro de la primera reespecificación de `c1e2`. Con el código anterior las llamadas son `respec-escena, respec-escena, replan, …`: dos reespecificaciones de escena antes de replanificar el tramo, con `CHAPTER_ATTEMPTS = 2`. Con el arreglo, una.

**R1 · La reanudación replanificaba desde el brief.** Riesgo sin contraejemplo formal, ver §6: el modelo no tiene contenido de escaleta.

- *Arreglo* (`91a1457`): `wm_run_state.outline` guarda la escaleta vigente tras planificar, tras cada replanificación de cuarentena y tras la puerta de acto y el Supervisor de cada capítulo. `_run_chapters` la lee con `load_outline` y solo llama a `_plan_with_gate` si no hay ninguna. Un fichero anterior a la migración 6 no la tiene y replanifica una vez, como antes.
- *Test*: `test_r1_…`. El Supervisor replanifica el capítulo 2 y la caída llega escribiendo `c2e1`. Con el código anterior el Arquitecto se llama dos veces y el capítulo 2 se escribe con la escaleta original; con el arreglo, una vez, y con la replanificada.

**Menor · `arc_replans > 2` en `_plan_with_gate`.** Arreglado en `91a1457` con `retries.ARC_REPLANS`: la escaleta tiene ahora 2 intentos, como `_replan`, y `PlanAttempts` pasa de 3 a 2 en todas las configuraciones.

### 7.2 Mutaciones: el modelo detecta lo que tiene que detectar

| Mutación | Cambio (marcado `MUTACION` en la copia) | Contraejemplo | Salida |
|---|---|---|---|
| `m1_freeze_sin_puerta` | Un delta que el Árbitro rechaza va a congelar, y `Freeze` no mira las puertas | `NeverPublishUngated`: el capítulo 1 congela con `deltaClean = FALSE` | `tlc/mutation_m1_freeze_sin_puerta.txt` |
| `m2_caidas_sin_tope` | `Crash` sin `crashes < MaxCrashes` | `GenerationTerminates` violada: un lazo `Crash` → `Resume` → `PlanPasses` → … → `Crash`, que TLC cierra con «Back to state N» | `tlc/mutation_m2_caidas_sin_tope.txt` |
| `m3_enmienda_sin_historial` | `AmendApplied` no guarda el texto anterior | `PreviousVersionPreserved`: la versión 1 cambia al crear la 2 | `tlc/mutation_m3_enmienda_sin_historial.txt` |
| `m4_save_sin_descartar` | `checkpoint.save` sin el `DELETE` de los borradores posteriores | `ResumeOnlyClosed`: tras una cuarentena, la escena 1 cierra y el borrador de la 2 sobrevive | `tlc/mutation_m4_save_sin_descartar.txt` |

M4 es la prueba de que `ResumeOnlyClosed` ya no es vacuo: con el borrado se cumple, sin él falla.

### 7.3 Contraejemplos durante el desarrollo, y el cambio que provocaron en el modelo

- **La guarda de retcon de `chapter.tla` no correspondía a nada del código.** Se quitó y se añadió `RetconPartial`. `RetconsBounded` prueba que la cota la da la escalera: `chapter` pasa con 1.831 estados.
- **`ResumeOnlyClosed == lastClosed <= scene` era cierto por construcción.** Se retiró de `chapter.tla` y se redefinió en `run.tla` sobre los borradores y el punto que reutiliza `Resume`. M4 prueba que no es vacuo.
- **Error de evaluación de TLC en `PlanPasses`.** `ckCh = 1 \/ freezes[ckCh - 1] >= 1` se evalúa por ramas y aplica `freezes` a 0. Se cambió por un `IF`.
- **Explosión del espacio de estados con 5 capítulos.** Se aplicó la reducción de §3.
- **B1 a B4.** Son fallos del código, no del modelo. Se documentan en §7.1 y se arreglaron en el código en `91a1457`, con un test por contraejemplo.
