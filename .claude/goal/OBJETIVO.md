Trabaja en este repositorio (Story-Maker) hasta que se cumplan a la vez las cuatro condiciones de <condicion_de_parada>. No te detengas antes ni des el objetivo por cumplido sin la evidencia que pide cada condición. La calidad manda: prefiero una tirada que tarda más a una obra con defectos aceptados.

<contexto>
- Las reglas del repositorio están en AGENTS.md. Síguelas en todo momento, sobre todo los procesos A, B y C (§6), la puerta `python gate.py` (en backend/) y `node gate.mjs` (en frontend/).
- La auditoría la hace el plugin auditoria-entrega con `/auditoria-entrega:auditar`. Deja el informe en .claude/auditoria-entrega/informe.md. Su escala tiene cinco estados: ❌ Ausente, 🟡 Especificado, 🟠 Implementado, ✅ Demostrado y ⚠️ En conflicto.
- Perfiles de extensión (backend/commons/types/length.py): `prueba` = 3 capítulos, `corta` = 5 y `breve` = 10.
- Hace poco rebajé los filtros de calidad para que las tiradas cortas terminaran. Esas rebajas son las decisiones D-128, D-131 y D-136 de specs/srs-backend-v4.md, y su implementación está en RF-274 y RF-284. Ya he decidido revertirlas: esta decisión es mía y está tomada, así que no hace falta que me la vuelvas a preguntar.
- Esta sesión puede cortarse por falta de créditos. Un guion externo, .claude/goal/vigilante.ps1, la reanuda cada 20 minutos con `claude --continue`. Por eso el progreso tiene que vivir en disco y no solo en tu contexto.
</contexto>

<estado_en_disco>
- Mantén .claude/goal/ESTADO.md al día. Actualízalo después de cada paso terminado y antes de lanzar cualquier cosa larga. Debe decir: el paso actual de <orden_de_trabajo>, lo que está hecho con su commit, la tirada en curso con su id, su perfil y su último capítulo congelado, y el siguiente paso concreto.
- Al reanudar, lee primero OBJETIVO.md, ESTADO.md e INTENTOS.md, y sigue desde ahí. No repitas lo que ya consta como hecho.
- Cuando se cumplan las cuatro condiciones, y solo entonces, crea el fichero vacío .claude/goal/HECHO. Es la señal para que el vigilante pare.
</estado_en_disco>

<archivo_de_intentos>
Todo intento de novela se conserva, también el que falla. Es el material con el que se mejora el sistema.
- Cada intento es una tirada nueva con su propio id y su propio fichero SQLite. Nunca sobrescribas, borres, limpies ni reutilices la carpeta de un intento anterior.
- Comprueba antes de la primera tirada que el espejo de Langfuse funciona: sus claves están en .env; léelas sin mostrarlas nunca. Cada intento tiene que quedar en Langfuse, además de en la traza local. Si Langfuse no responde, la traza local sigue siendo la fuente de verdad (AGENTS.md §1): la tirada sigue, apúntalo en el índice y vuelve a exportar esa traza cuando Langfuse responda.
- Mantén el índice .claude/goal/INTENTOS.md, con una fila por intento: nº | fecha | perfil | id de la tirada | commit del código | resultado (cerrada estricta, fallida o cortada por créditos) | capítulos congelados | mediana del Jurado por capítulo | coste | tiempo | causa raíz del fallo | qué se cambió después | ruta del SQLite y de la traza local | enlace o id de la traza en Langfuse.
- Antes de arreglar nada tras un fallo, lee los intentos anteriores del índice y sus trazas. Busca el patrón que se repite: un mismo defecto en varios intentos es una causa raíz, no mala suerte.
</archivo_de_intentos>

<escalera_de_novelas>
Las novelas se escriben de una en una y en este orden. Cada escalón sirve para no gastar tiempo en una obra larga mientras la corta todavía falla.
1. `prueba` (3 capítulos). Si no cierra en estricto, arregla la causa raíz y lánzala otra vez. Repite hasta que cierre. No lances `corta` ni `breve` mientras tanto.
2. `corta` (5 capítulos). Solo cuando `prueba` haya cerrado en estricto. Si falla, arregla la causa y relánzala a ella; no vuelvas a `prueba` salvo que el arreglo toque algo que `prueba` ejercita, y en ese caso relanza `prueba` primero.
3. `breve` (10 capítulos). Solo cuando `corta` haya cerrado en estricto, con la misma regla.
Si al arreglar un escalón cambias código que afecta a un escalón ya cerrado, ese escalón vuelve a lanzarse antes de seguir. Las tres obras que cuentan para la condición 4 tienen que estar escritas con el mismo código que la última puerta en verde.
</escalera_de_novelas>

<sin_creditos>
El motor escribe con la misma suscripción que esta sesión, así que se queda sin créditos a la vez que ella.
- Si una tirada cae y la traza o la salida del proveedor dicen límite de uso, créditos agotados, rate limit o sobrecarga, eso NO es un defecto del sistema. No toques código, prompts ni umbrales por ello. Regístralo en INTENTOS.md como «cortada por créditos» y no lo cuentes como fallo.
- Reanuda esa tirada desde su último capítulo congelado con el mecanismo de reanudación que ya existe (checkpoint, CAN-12). No la empieces de cero.
- Si la sesión sigue viva, espera 20 minutos con ScheduleWakeup antes de reintentar. Si no sigue viva, el vigilante te reanudará.
- Arranca el backend y el frontend como procesos independientes de la sesión (Start-Process), para que sobrevivan a un corte. Al reanudar, comprueba que responden y relánzalos si no.
</sin_creditos>

<restaurar_filtros>
Esto es lo primero que haces, antes de lanzar ninguna tirada.
1. Proceso B sobre specs/srs-backend-v4.md: marca D-128, D-131 y D-136 como revertidas, con su motivo («el sistema debe ser estricto en todos los perfiles»). No las borres (AGENTS.md §5.1). Ajusta RF-274, RF-284 y las filas del registro de riesgo aceptado que dependen de ellas, y propaga el cambio a docs/verification.md §9 y a backend/PLAN.md §7.
2. Proceso C: en todos los perfiles, `lenient = False`. El umbral del Jurado vuelve a mediana 3, la cita mínima a 8 palabras y el conjunto dorado a los casos de `novela`. Los rangos de palabras y el número de capítulos de cada perfil no se tocan.
3. No reviertas D-130 ni D-140. Esas dos no rebajan nada: descartan con su motivo lo que es inválido, y eso es fallo cerrado.
4. Si al restaurar un filtro aparece un conflicto real (por ejemplo, que un perfil de 3 capítulos no tenga fragmentos para 5 casos dorados, D-112), anota la pregunta en ESTADO.md con el formato de AGENTS.md §6.6. No inventes un número intermedio.
5. Busca cualquier otra rebaja de umbral, tolerancia o bypass que se haya introducido para que las tiradas pasen. Si encuentras alguna, no la toques: enuméramela en ESTADO.md.
</restaurar_filtros>

<condicion_de_parada>
1. FILTROS RESTAURADOS: ningún perfil tiene `lenient = True`. El Jurado usa mediana 3 y citas de 8 palabras en todos los perfiles. La puerta del backend y la del frontend están en verde con esos valores.
2. AUDITORÍA: la última ejecución completa de `/auditoria-entrega:auditar`, hecha con --run y sin --rapido sobre el commit actual, no deja ningún ENT-NN en ❌, 🟡 ni 🟠. Solo vale ✅ con cita localizable. Un ⚠️ se acepta únicamente si su defensa por escrito consta en el informe y no se puede resolver sin una decisión mía.
3. SISTEMA EN MARCHA: el backend (FastAPI) y el frontend (Vite, `npm run dev`) están arrancados a la vez. El frontend se conecta al backend sin errores en consola.
4. TRES NOVELAS TERMINADAS EN MODO ESTRICTO: los tres escalones de <escalera_de_novelas> han cerrado, con modelo real y con el código de la última puerta en verde. Cada obra debe cumplir todo esto:
   - Todos sus capítulos están congelados y la obra está cerrada por la condición estricta de RF-23. El `reason` de `work.close` no empieza por «pendiente: ».
   - Su traza no contiene ni un solo registro `scene.forced`, `chapter.forced` ni `replan.kept`.
   - Cada capítulo pasó el Jurado con mediana ≥ 3 y la puerta de capítulo sin S1 abiertos.
   - Está en Langfuse y en INTENTOS.md, y se puede leer entera en el frontend.
</condicion_de_parada>

<orden_de_trabajo>
1. Ejecuta <restaurar_filtros> y pasa las dos puertas.
2. Lanza la auditoría y lee el camino crítico y la ola 1 del informe.
3. Arranca el backend y el frontend según <sin_creditos>, comprueba Langfuse y lanza el primer escalón, `prueba`. Vigílalo con Monitor, no con sleep.
4. Mientras corre, resuelve los ENT-NN pendientes en el orden del camino crítico, usando el prompt de solución de su ficha. No cambies código que use la tirada en curso hasta que termine. Tras cada arreglo, pasa la puerta y relanza `/auditoria-entrega:check` solo sobre ese ENT-NN.
5. Cuando termine un intento, regístralo en INTENTOS.md. Si falló por algo que no es la falta de créditos, lee su traza, local y en Langfuse, junto con los intentos anteriores: qué verificador bloqueó, qué agente falló y por qué. Arregla la causa: el prompt del agente, la escaleta, el paquete de contexto o el código. Después sigue la <escalera_de_novelas>.
6. Cuando se cumplan las condiciones 1, 3 y 4, lanza la auditoría completa una última vez. Las tiradas terminadas forman parte de la evidencia.
</orden_de_trabajo>

<reglas>
- Prohibido hacer trampa para cumplir la condición: no edites la rúbrica, el plugin ni la config de auditoría. No bajes umbrales, rangos ni severidades. No vuelvas a activar `lenient`. No añadas excepciones por perfil. No marques estados a mano. Si un filtro bloquea, se arregla lo que produce el texto, no el filtro.
- Una tirada fallida no se da por terminada, no se borra y no se sustituye por una de otro perfil.
- Si un arreglo cruza el umbral de AGENTS.md §6.1 (decisión con dueño, número, ID o frontera nueva) y no es la reversión ya decidida, anota la pregunta en ESTADO.md con el formato de §6.6 y sigue con todo lo que no dependa de ella.
- No crees HECHO si queda alguna pregunta abierta en ESTADO.md.
- Nunca muestres ni copies el contenido de .env ni ninguna clave.
- Haz un commit por cada paso (restauración de filtros, cada ENT-NN, cada arreglo tras un intento), con mensaje descriptivo. No hagas push.
</reglas>

<informe_final>
Escríbelo en .claude/goal/INFORME.md antes de crear HECHO:
- Qué filtros restauraste, con el fichero y la línea de cada uno, y cualquier otra rebaja que encontraste sin tocarla.
- Una tabla ENT-NN | estado antes | estado ahora | evidencia.
- Un resumen de INTENTOS.md: cuántos intentos hizo cada perfil, qué causas raíz aparecieron y qué arreglo cerró cada una.
- Para cada una de las tres obras finales: el perfil, el id, las palabras, la mediana del Jurado por capítulo, el coste, el tiempo, su traza en Langfuse y la ruta de su SQLite.
- Las URLs del backend y del frontend en marcha.
- Lo que resolviste por tu cuenta eligiendo entre dos lecturas posibles, y cualquier ⚠️ que siga abierto con su defensa.
</informe_final>
