#!/usr/bin/env bash
# Ejecuta TLC sobre todo el modelo y guarda cada salida en tlc/. VER-18.
#
#   bash run_tlc.sh            # todo
#   bash run_tlc.sh run        # solo los nombres que empiezan por "run"
#
# Necesita java 11 o mayor y tla2tools.jar. Por defecto usa las rutas de la
# maquina de la entrega; se cambian con JAVA y TLA2TOOLS_JAR.
#
# Esperado: chapter y run sin error; run_reach, code-today/* y mutations/* con
# su contraejemplo. El script falla si alguno no da lo esperado (fallo cerrado).
set -u
cd "$(dirname "$0")"

JAVA="${JAVA:-/c/Program Files/Eclipse Adoptium/jdk-21.0.12.101-hotspot/bin/java.exe}"
JAR="${TLA2TOOLS_JAR:-C:/tools/tla/tla2tools.jar}"
META="${TMPDIR:-${TEMP:-/tmp}}/story-maker-tlc"
FILTER="${1:-}"
MODEL_DIR="$(pwd -W 2>/dev/null || pwd)"
COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo desconocido)"
DIRTY="$(git status --porcelain -- . 2>/dev/null | grep -q . && echo ' (con cambios sin commitear en model/)' || true)"
VERSION="$("$JAVA" -cp "$JAR" tlc2.TLC -h 2>&1 | grep -m1 -o 'Version [0-9.]* of [0-9A-Za-z ]*' || echo desconocida)"
mkdir -p tlc
fallos=0

# nombre, directorio, modulo, cfg, lo que tiene que aparecer en la salida
check() {
    local name="$1" dir="$2" module="$3" cfg="$4" expect="$5"
    [[ -n "$FILTER" && "$name" != "$FILTER"* ]] && return
    local out="tlc/$name.txt"
    local cmd="java -XX:+UseParallelGC -DTLA-Library=<model> -cp tla2tools.jar tlc2.TLC -config $cfg -workers auto $module.tla   (en $dir)"
    {
        echo "# $name"
        echo "# commit: $COMMIT$DIRTY"
        echo "# fecha: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
        echo "# TLC: $VERSION"
        echo "# comando: $cmd"
        echo "# esperado: $expect"
        echo
    } > "$out"
    (cd "$dir" && "$JAVA" -XX:+UseParallelGC -DTLA-Library="$MODEL_DIR" -cp "$JAR" tlc2.TLC \
        -config "$cfg" -workers auto -metadir "$META/$name" "$module.tla") >> "$out" 2>&1
    if grep -q -- "$expect" "$out"; then
        echo "ok     $name: $expect"
    else
        echo "FALLO  $name: no aparece «$expect», ver $out"
        fallos=$((fallos + 1))
    fi
}

check chapter  . chapter chapter.cfg   "No error has been found"
check run      . run     run.cfg       "No error has been found"
check run_reach . run    run_reach.cfg "Invariant NeverPublished is violated"

check code-today_b1_double_freeze        . run code-today/b1_double_freeze.cfg        "Invariant NoChapterDuplicated is violated"
check code-today_b2_retcon_history       . run code-today/b2_retcon_history.cfg       "Invariant PreviousVersionPreserved is violated"
check code-today_b3_checkpoint           . run code-today/b3_checkpoint.cfg           "Invariant ResumeOnlyClosed is violated"
check code-today_b3_blocked_scene_frozen . run code-today/b3_blocked_scene_frozen.cfg "Invariant NeverPublishUngated is violated"
check code-today_b4_budget               . run code-today/b4_budget.cfg               "Invariant RetriesWithinLimit is violated"

check mutation_m1_freeze_sin_puerta      mutations m1_freeze_sin_puerta      m1_freeze_sin_puerta.cfg      "Invariant NeverPublishUngated is violated"
check mutation_m2_caidas_sin_tope        mutations m2_caidas_sin_tope        m2_caidas_sin_tope.cfg        "Temporal properties were violated"
check mutation_m3_enmienda_sin_historial mutations m3_enmienda_sin_historial m3_enmienda_sin_historial.cfg "Invariant PreviousVersionPreserved is violated"
check mutation_m4_save_sin_descartar     mutations m4_save_sin_descartar     m4_save_sin_descartar.cfg     "Invariant ResumeOnlyClosed is violated"

exit "$fallos"
