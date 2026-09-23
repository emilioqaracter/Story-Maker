#!/usr/bin/env python
"""La puerta: todas las comprobaciones que un cambio tiene que pasar.

Existe como **un solo comando** a proposito. Mientras la puerta fue una lista
de comandos que alguien ejecutaba a mano, "la puerta pasa" significaba "paso
cuando la ejecute", que es bastante menos de lo que suena: basta olvidarse de
uno para que entre codigo roto sin que nadie se entere.

    python gate.py          # todo lo que corre en cada cambio
    python gate.py --full   # anade lo lento: mutacion y auditoria de paquetes

Las comprobaciones lentas van fuera del paso normal porque tardan minutos y se
ejecutarian decenas de veces al dia sin encontrar nada nuevo. Corren en la
integracion continua por su cuenta.
"""

from __future__ import annotations

import argparse
import json

# Solo ejecuta la lista fija de CHECKS; no entra nada del exterior.
import subprocess  # nosec B404
import sys
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class Check:
    name: str
    what: str
    command: list[str]
    slow: bool = False
    #: Como se decide si paso. Por defecto, el codigo de salida. Algunas
    #: herramientas necesitan otra cosa: ver `seguridad del codigo`.
    judge: str = "returncode"


CHECKS: tuple[Check, ...] = (
    Check(
        name="coherencia docs-spec-plan",
        what="Contrasta specs/, backend/PLAN.md y docs/ entre si: IDs, secciones, "
        "matrices y tramos. Es el ciclo de AGENTS.md 6.7 hecho codigo",
        command=["python", "coherence.py"],
    ),
    Check(
        name="contrato versionado",
        what="El esquema OpenAPI del repositorio es el que genera la aplicacion: "
        "de el sale el cliente del frontend (RI-08, RI-54)",
        command=["python", "-m", "orchestration.openapi", "--check"],
    ),
    Check(
        name="formato y estilo",
        what="Lee el codigo sin ejecutarlo buscando formas propensas a error",
        command=["python", "-m", "ruff", "check", "."],
    ),
    Check(
        name="tipos",
        what="Comprueba que las piezas encajan antes de ejecutar nada",
        command=["python", "-m", "mypy", "."],
    ),
    Check(
        name="fronteras entre carpetas",
        what="Impide que una funcionalidad importe de otra; es lo unico que evita "
        "que el paquete por funcionalidad se vuelva capas tecnicas con otro nombre",
        command=["lint-imports"],
    ),
    Check(
        name="seguridad del codigo",
        what="Busca patrones inseguros: consultas concatenadas, secretos, aleatoriedad debil",
        # Se juzga por HALLAZGOS y no por codigo de salida. Bandit sale con 1
        # tambien cuando encuentra una supresion que funciono: con sentencias
        # multilinea reporta el problema en una linea y la supresion va en otra,
        # asi que avisa de ella *porque* surtio efecto. Es circular y no hay
        # forma de evitarlo colocando mejor el comentario. Lo que importa es si
        # queda algun hallazgo real, y eso se lee de su JSON.
        command=[
            "python",
            "-m",
            "bandit",
            "-q",
            "-r",
            ".",
            # B101 es `assert`, que en pruebas es la forma de escribirlas.
            # B608 lo sustituye `commons/test_sql_safety.py`, que comprueba QUE
            # se interpola en cada consulta en vez de si se usa f-string. Mas
            # estricta, no menos: la generica se silencia por linea y se olvida;
            # la nuestra obliga a declarar cada caso en un sitio visible.
            "--skip",
            "B101,B608",
            "--exclude",
            "./.venv,./build",
            "-f",
            "json",
        ],
        judge="bandit",
    ),
    Check(
        name="pruebas y propiedades",
        what="Casos concretos, reglas que la maquina intenta romper generando cientos, "
        "y peticiones generadas desde el propio contrato de la API",
        command=["python", "-m", "pytest", "-q"],
    ),
    Check(
        name="vulnerabilidades en dependencias",
        what="Contrasta las librerias instaladas contra vulnerabilidades conocidas",
        command=["python", "-m", "pip_audit", "--skip-editable"],
        slow=True,
    ),
)


def run(check: Check) -> tuple[bool, float]:
    start = time.monotonic()
    # Los comandos son constantes de este modulo; no entra nada del exterior.
    result = subprocess.run(check.command, capture_output=True, text=True)  # nosec B603
    elapsed = time.monotonic() - start

    if check.judge == "bandit":
        ok, detalle = _judge_bandit(result.stdout)
        if not ok:
            sys.stdout.write(detalle)
        return ok, elapsed

    ok = result.returncode == 0
    if not ok:
        sys.stdout.write(result.stdout)
        sys.stderr.write(result.stderr)
    return ok, elapsed


def _judge_bandit(raw: str) -> tuple[bool, str]:
    """Pasa si no queda ningun hallazgo, aunque el codigo de salida sea 1."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return False, f"bandit no devolvio JSON:\n{raw[:500]}\n"

    hallazgos = data.get("results", [])
    if not hallazgos:
        return True, ""

    lineas = [
        f"  [{h['issue_severity']}] {h['test_id']} {h['filename']}:{h['line_number']}"
        f"\n      {h['issue_text']}"
        for h in hallazgos
    ]
    return False, "\n".join(lineas) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="incluye las comprobaciones lentas")
    args = parser.parse_args()

    selected = [c for c in CHECKS if args.full or not c.slow]
    failed: list[str] = []

    for check in selected:
        print(f"  {check.name} ... ", end="", flush=True)
        ok, elapsed = run(check)
        print(f"{'OK' if ok else 'FALLA'}  ({elapsed:.1f}s)")
        if not ok:
            failed.append(check.name)

    print()
    if failed:
        print(f"PUERTA EN ROJO: {', '.join(failed)}")
        return 1
    print(f"PUERTA EN VERDE: {len(selected)} comprobaciones")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
