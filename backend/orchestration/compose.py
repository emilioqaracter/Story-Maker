"""Arranque de una tirada real: compone el motor y corre hasta el cierre.

RF-66, RF-101, RF-104, RNF-03. Es lo que la ruta de arranque ejecuta en su
hilo, y lo que una linea de ordenes puede llamar directamente.

Antes de la primera llamada pasan dos comprobaciones de arranque, y las dos
son fallo cerrado: el modelo de embeddings carga y su dimension cuadra con la
del indice (RF-101), y el factor del contador se calibra contra una llamada
real (RF-104). Sin ellas no se admite ninguna llamada.

Cada invocacion --una tirada o la aplicacion de enmiendas fuera de ella-- se
engancha al espejo de Langfuse si hay claves, o deja `export.disabled` si no, y
al acabar, cierre o aborto, deja `work.cost` con los tokens y el coste totales
de la novela (`specs/srs-backend-v4.md` RF-235, RI-60). El espejo nunca decide:
si no responde, la tirada es la misma.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

from canon.brief import Brief, load_brief
from canon.db import connection
from commons.provider.claude_cli import ClaudeCli
from commons.provider.embeddings import LocalEmbedder, load_backend
from commons.tokens.calibration import calibrate
from commons.tokens.counter import TokenCounter
from commons.tokens.factors import DEFAULT_FACTOR, ModelFactors
from commons.tracing.langfuse_export import attach_live_export, work_cost
from commons.tracing.trace import Trace
from orchestration.admission import Admission
from orchestration.engine import Composer, specs_provider
from orchestration.loop import RunReport, run
from planning.outline.types import CHAPTER_WORDS


def chapters_for(brief: Brief) -> int:
    """Cuantos capitulos planificar: la extension pedida sobre el capitulo tipico.

    El capitulo tipico es el punto medio de EST-07. No es un numero nuevo: es
    la unica lectura del rango que el brief no fija y la escaleta necesita.
    """
    tipico = (CHAPTER_WORDS[0] + CHAPTER_WORDS[1]) // 2
    return max(1, round(brief.target_words / tipico))


def real_counter(port: ClaudeCli, sample: str, model_id: str) -> int:
    """Recuento real por llamada: el CLI no cuenta sin llamar.

    Se le pide al modelo una respuesta minima con la muestra delante y se lee el
    `usage`, descontando el andamiaje del CLI (D-35). Es lo que RF-104 pide:
    contrastar `tiktoken` contra lo que el proveedor cobra de verdad.
    """
    c = port.complete_once(
        cacheable_prefix="Responde exactamente OK.",
        packet=sample,
        instruction="Responde OK.",
        output_schema="",
        max_output_tokens=20,
    )
    return max(1, c.usage.total_input - c.harness_tokens)


Invocation = Literal["run", "amend"]


def compose_engine(
    path: Path, trace: Trace, *, model: str = "haiku", invocation: Invocation = "run"
) -> tuple[Composer, Brief]:
    """El motor real sobre un fichero, con sus dos comprobaciones de arranque.

    `invocation` va en el registro `calibration`, que es el primero de cada
    invocacion: es lo que separa una generacion de la siguiente en el espejo
    (RF-234).
    """
    brief = load_brief(path)
    port = ClaudeCli(model=model)

    with connection.reader(path) as con:
        row = con.execute(
            "SELECT vector_dim FROM prose_chunk WHERE vector_dim IS NOT NULL LIMIT 1"
        ).fetchone()
    embedder = LocalEmbedder(load_backend())
    embedder.verify(index_dimension=row["vector_dim"] if row else None)

    factors = ModelFactors()
    muestra = (brief.style_guide + "\n" + brief.rulebook + "\n" + brief.title) * 3
    resultado = calibrate(
        sample=muestra,
        model_id=model,
        real_counter=lambda s, m: real_counter(port, s, m),
        factors=factors,
    )
    if resultado.ratio < 1.0:
        # El `usage` del CLI no aisla la muestra del andamiaje (medido: la
        # muestra "costo" 43 tokens). Un factor por debajo de 1 dejaria el
        # estimador corto por construccion, asi que rige el suelo declarado de
        # `factors.py` y queda trazado que la calibracion no valio.
        factors.set(model, DEFAULT_FACTOR)
        trace.emit(
            "calibration",
            model=model,
            factor=DEFAULT_FACTOR,
            ratio=resultado.ratio,
            fallback=True,
            invocation=invocation,
        )
    else:
        trace.emit(
            "calibration",
            model=model,
            factor=resultado.factor,
            ratio=resultado.ratio,
            invocation=invocation,
        )

    composer = Composer(
        port=port,
        path=path,
        brief=brief,
        embedder=embedder,
        counter=TokenCounter(factors),
        model_id=model,
        trace=trace,
        admission=Admission(trace=trace),
    )
    return composer, brief


#: Quien compone el motor. Las pruebas lo sustituyen por uno con dobles; la
#: tirada real usa `compose_engine`.
ComposeEngine = Callable[..., tuple[Composer, Brief]]


def _close_invocation(trace: Trace, invocation: Invocation) -> None:
    """RF-235. `work.cost`: tokens y coste totales de la novela, desde su traza.

    Se emite al acabar la invocacion, cierre o aborto, porque es lo que cierra
    su generacion en el espejo. No espera a la red: lo que el espejo no llegue a
    enviar sigue en el JSONL (RNF-53).
    """
    trace.emit("work.cost", invocation=invocation, **work_cost(trace.read()))


def run_novel(
    path: Path,
    novel_id: str,
    trace: Trace,
    *,
    model: str = "haiku",
    compose: ComposeEngine = compose_engine,
) -> RunReport:
    """Del fichero al cierre de obra, sin intervencion (RNF-03)."""
    from orchestration.amend import apply_pending

    attach_live_export(trace)
    try:
        composer, brief = compose(path, trace, model=model, invocation="run")
        engine = composer.engine()
        return run(
            path,
            brief,
            engine,
            novel_id=novel_id,
            chapters=chapters_for(brief),
            specs_for=specs_provider(composer),
            trace=trace,
            after_freeze=lambda: apply_pending(path, engine, trace),
        )
    finally:
        _close_invocation(trace, "run")


def amend_novel(
    path: Path,
    novel_id: str,
    trace: Trace,
    *,
    model: str = "haiku",
    compose: ComposeEngine = compose_engine,
) -> None:
    """RF-223. Sin tirada en marcha: aplica las enmiendas pendientes con el motor real."""
    from orchestration.amend import apply_pending, drain, reject_queued

    attach_live_export(trace)
    try:
        try:
            composer, _brief = compose(path, trace, model=model, invocation="amend")
        except Exception as exc:
            # RF-226: sin motor no se aplica nada, y lo pendiente no queda esperando.
            reject_queued(
                path, f"No se pudo preparar el sistema para aplicarla: {exc}"[:300], trace
            )
            raise
        engine = composer.engine()
        drain(path, lambda: apply_pending(path, engine, trace))
    finally:
        _close_invocation(trace, "amend")


def main(argv: list[str] | None = None) -> int:
    """`python -m orchestration.compose --novel-id ID --brief brief.json [--runs DIR]`.

    Crea la novela si no existe, la corre hasta el cierre e imprime el informe.
    Es la misma tirada que arranca `POST /novels/{id}/run`, sin servidor delante.
    """
    import argparse
    import json

    from canon.brief import create_novel
    from commons.settings import Settings
    from orchestration.loop import as_json

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--novel-id", required=True)
    parser.add_argument("--brief", required=True, type=Path)
    parser.add_argument("--runs", type=Path, default=None)
    parser.add_argument("--model", default="haiku")
    args = parser.parse_args(argv)

    settings = Settings(runs_dir=args.runs) if args.runs else Settings.from_env()
    path = settings.novel_path(args.novel_id)
    if not path.exists():
        brief = Brief.model_validate_json(args.brief.read_text(encoding="utf-8"))
        create_novel(path, brief)
    trace = Trace(settings.trace_path(args.novel_id))
    report = run_novel(path, args.novel_id, trace, model=args.model)
    print(as_json(report))
    print(json.dumps({"closed": report.closed, "reason": report.reason}, ensure_ascii=False))
    return 0 if report.closed else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
