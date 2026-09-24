#!/usr/bin/env python
"""Hook `PreToolUse` de Claude Code: la politica de las acciones de desarrollo.

`specs/srs-backend-v4.md` RF-252, RF-253, RI-66, RNF-56, D-92.

Cuatro reglas en orden; **gana la primera que casa**, igual que la precedencia
de PRO-10: un orden total, sin empates ni a quien preguntar.

1. `canon-solo-lo-escribe-la-congelacion`: deniega escribir un `*.sqlite` bajo
   `backend/runs-*/` o `backend/golden/`. El canon solo lo escribe el Archivero
   al congelar (AGENTS.md 5.3.3); una edicion a mano es verdad sin procedencia.
2. `secretos-no-se-leen`: deniega leer `.env*` o un fichero de claves.
3. `capitulo-sin-prohibidas-globales`: deniega escribir un fichero de capitulo
   que contiene un termino de la lista global, con `check.forbidden` del motor.
4. `por-defecto`: permite todo lo demas.

**Cada decision se registra**, tambien las que permiten, en el audit log de
desarrollo `.claude/audit/policy.jsonl`, con la misma cadena de hashes que la
traza del motor (`commons.tracing.trace`, RF-253): decision, regla, herramienta,
ruta e instante. Nunca el contenido del fichero ni el texto de un comando: un
comando puede llevar un secreto, y el audit log no puede ser donde se filtre.

Salida, en el formato de decision de Claude Code: un `deny` devuelve el JSON con
`permissionDecision` y su motivo. El `allow` de la regla 4 queda en el audit log
pero **no se devuelve** a Claude Code: alli `allow` salta las preguntas de
permiso y las reglas `deny` del usuario, y una politica que solo deniega no
tiene por que abrir lo que el resto de la configuracion cierra. Sin decision,
sigue el flujo normal de permisos.

**Falla cerrado** (RNF-56, AGENTS.md 5.3.6): si no puede evaluar, importar el
backend o escribir el audit log, deniega y sale con 2, que Claude Code trata
como bloqueo pase lo que pase.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import IO, Any

REPO = Path(__file__).resolve().parents[2]
BACKEND = REPO / "backend"

#: Dentro de `.claude/` del proyecto. Ignorado por git: es de cada maquina.
AUDIT_REL = Path(".claude") / "audit" / "policy.jsonl"

CHAPTER_SUFFIXES = (".chapter.md", ".chapter.txt")
WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit"})

R_CANON = "canon-solo-lo-escribe-la-congelacion"
R_SECRETS = "secretos-no-se-leen"
R_GLOBAL = "capitulo-sin-prohibidas-globales"
R_DEFAULT = "por-defecto"
R_CLOSED = "fallo-cerrado"

#: Ficheros de claves por nombre. `.env*` va aparte porque es un prefijo.
_KEY_NAMES = re.compile(r"^(id_(rsa|dsa|ecdsa|ed25519)(\.pub)?|.*\.(pem|key|p12|pfx))$", re.I)

#: En un comando: `.env`, `.env.local`... como palabra suelta o final de ruta.
_BASH_ENV = re.compile(r"(?:^|[\s/\\'\"=<>|;&(])\.env[\w.-]*(?=$|[\s'\"|;&)<>])")
_BASH_KEY = re.compile(
    r"(?:^|[\s/\\'\"=<>|;&(])(?:id_(?:rsa|dsa|ecdsa|ed25519)|[\w.-]+\.(?:pem|key|p12|pfx))"
    r"(?=$|[\s'\"|;&)<>])",
    re.I,
)

#: En un comando: un SQLite de tirada o del conjunto dorado.
_BASH_CANON = re.compile(
    r"(?:backend[/\\]+)?(?:runs-[^/\\\s'\"]+|golden)[/\\][^\s'\"]*\.sqlite(?:-wal|-shm|-journal)?",
    re.I,
)
#: Lo que en un comando escribe o destruye. Leer un canon con `sqlite3 -readonly`
#: o copiarlo fuera no casa: solo lo que puede cambiarlo.
_BASH_WRITES = re.compile(
    r"(>|\b(cp|mv|rm|del|tee|dd|truncate|touch|shred|sed\s+-i|Remove-Item|Set-Content|"
    r"Add-Content|Out-File|Copy-Item|Move-Item|Clear-Content)\b|\bsqlite3\b(?!\s+-readonly))",
    re.I,
)


@dataclass(frozen=True)
class Decision:
    decision: str  # allow | deny
    rule: str
    reason: str
    target: str = ""


def _parts(path: str) -> list[str]:
    return [p for p in re.split(r"[/\\]+", path) if p]


def is_canon_sqlite(path: str) -> bool:
    """Un `*.sqlite` (o su WAL) bajo `backend/runs-*/` o `backend/golden/`."""
    partes = _parts(path)
    if not partes or not re.search(r"\.sqlite(-wal|-shm|-journal)?$", partes[-1], re.I):
        return False
    return any(
        a.lower() == "backend" and (b.lower() == "golden" or b.lower().startswith("runs-"))
        for a, b in pairwise(partes)
    )


def is_secret(path: str) -> bool:
    partes = _parts(path)
    if not partes:
        return False
    nombre = partes[-1]
    return nombre.lower().startswith(".env") or bool(_KEY_NAMES.match(nombre))


def is_chapter(path: str) -> bool:
    return path.replace("\\", "/").lower().endswith(CHAPTER_SUFFIXES)


def _resolve(path: str, cwd: str | None) -> str:
    p = Path(path)
    return str(p if p.is_absolute() or not cwd else Path(cwd) / p)


def _written_texts(tool: str, entrada: dict[str, Any]) -> list[str]:
    """Lo que la herramienta va a escribir: `content`, o el texto nuevo de cada edicion."""
    if tool == "Write":
        return [str(entrada.get("content") or entrada.get("file_text") or "")]
    textos = [entrada.get("new_string"), entrada.get("new_str")]
    for e in entrada.get("edits") or []:
        if isinstance(e, dict):
            textos += [e.get("new_string"), e.get("new_str")]
    return [t for t in textos if isinstance(t, str)]


def _write_targets(entrada: dict[str, Any]) -> list[str]:
    rutas = [entrada.get("file_path")]
    rutas += [e.get("file_path") for e in entrada.get("edits") or [] if isinstance(e, dict)]
    return [r for r in rutas if isinstance(r, str) and r]


def global_terms() -> tuple[Any, ...]:
    """La lista global versionada, como `ForbiddenTerm` de nivel `global`."""
    from canon.brief import read_global_forbidden
    from verification.checks.forbidden import ForbiddenTerm

    return tuple(ForbiddenTerm(term=t, level="global") for t in read_global_forbidden())


def decide(payload: dict[str, Any], *, terms: tuple[Any, ...] | None = None) -> Decision:
    """Las cuatro reglas en orden. `terms` sustituye a la lista global en pruebas."""
    tool = str(payload.get("tool_name") or "")
    entrada = payload.get("tool_input") or {}
    if not isinstance(entrada, dict):
        raise ValueError("tool_input no es un objeto")
    cwd = payload.get("cwd") if isinstance(payload.get("cwd"), str) else None

    rutas = [_resolve(r, cwd) for r in _write_targets(entrada)] if tool in WRITE_TOOLS else []
    comando = str(entrada.get("command") or "") if tool == "Bash" else ""

    # 1. El canon solo lo escribe la congelacion.
    for ruta in rutas:
        if is_canon_sqlite(ruta):
            return Decision("deny", R_CANON, "el canon solo lo escribe la congelacion", ruta)
    if comando:
        m = _BASH_CANON.search(comando)
        if m and _BASH_WRITES.search(comando):
            return Decision("deny", R_CANON, "el canon solo lo escribe la congelacion", m.group(0))

    # 2. Los secretos no se leen.
    if tool == "Read":
        ruta = _resolve(str(entrada.get("file_path") or ""), cwd)
        if is_secret(ruta):
            return Decision("deny", R_SECRETS, "no se leen .env ni ficheros de claves", ruta)
    if comando:
        m = _BASH_ENV.search(comando) or _BASH_KEY.search(comando)
        if m:
            objetivo = m.group(0).strip(" /\\'\"=<>|;&(")
            return Decision("deny", R_SECRETS, "no se leen .env ni ficheros de claves", objetivo)

    # 3. Un capitulo no lleva prohibidas globales.
    capitulos = [r for r in rutas if is_chapter(r)]
    if capitulos:
        from verification.checks.forbidden import check_forbidden

        lista = global_terms() if terms is None else terms
        for texto in _written_texts(tool, entrada):
            defectos = check_forbidden(texto, terms=lista)
            if defectos:
                d = defectos[0]
                return Decision(
                    "deny",
                    R_GLOBAL,
                    f"{d.rule}: «{d.evidence.quote}» @{d.evidence.offset}",
                    capitulos[0],
                )

    # 4. Todo lo demas.
    objetivo = rutas[0] if rutas else str(entrada.get("file_path") or "")
    return Decision("allow", R_DEFAULT, "ninguna regla lo deniega", objetivo)


def audit_path() -> Path:
    """`$CLAUDE_PROJECT_DIR/.claude/audit/policy.jsonl`, o el de este repositorio."""
    raiz = os.environ.get("CLAUDE_PROJECT_DIR") or str(REPO)
    return Path(raiz) / AUDIT_REL


def _try_lock(fh: IO[bytes]) -> None:
    """Toma el cerrojo sin esperar; lanza `OSError` si otro lo tiene."""
    if sys.platform == "win32":
        import msvcrt

        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(fh: IO[bytes]) -> None:
    if sys.platform == "win32":
        import msvcrt

        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


@contextmanager
def _file_lock(path: Path) -> Iterator[None]:
    """Cerrojo entre procesos: Claude Code puede lanzar varios hooks a la vez.

    Sin el, dos procesos leerian la misma ultima linea y la cadena se bifurcaria.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as fh:
        limite = time.monotonic() + 10
        while True:
            try:
                _try_lock(fh)
                break
            except OSError:
                if time.monotonic() > limite:
                    raise
                time.sleep(0.02)
        try:
            yield
        finally:
            _unlock(fh)


def record(payload: dict[str, Any], decision: Decision) -> None:
    """Una linea en el audit log, encadenada. Lanza si no queda escrita."""
    from commons.tracing.trace import Trace

    path = audit_path()
    with _file_lock(path.with_suffix(".lock")):
        traza = Trace(path)
        traza.emit(
            "policy.decision",
            decision=decision.decision,
            rule=decision.rule,
            reason=decision.reason[:300],
            tool=str(payload.get("tool_name") or ""),
            target=decision.target[:300],
            session_id=str(payload.get("session_id") or ""),
            tool_use_id=str(payload.get("tool_use_id") or ""),
        )
    if traza.failures:
        raise OSError(f"no se pudo escribir el audit log en {path}")


def _deny_output(decision: Decision) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"{decision.rule}: {decision.reason}",
            }
        },
        ensure_ascii=False,
    )


def _read_stdin() -> str:
    if sys.stdin is None or sys.stdin.isatty():
        return ""
    return sys.stdin.buffer.read().decode("utf-8")


def run(stdin: str) -> int:
    if str(BACKEND) not in sys.path:
        sys.path.insert(0, str(BACKEND))
    payload: dict[str, Any] = {}
    try:
        leido = json.loads(stdin)
        if not isinstance(leido, dict):
            raise ValueError("la entrada del hook no es un objeto JSON")
        payload = leido
        decision = decide(payload)
    except Exception as exc:
        return _closed(payload, f"no se pudo evaluar la politica ({type(exc).__name__}: {exc})")
    try:
        record(payload, decision)
    except Exception as exc:
        return _closed(payload, f"no se pudo registrar la decision ({type(exc).__name__}: {exc})")
    if decision.decision == "deny":
        sys.stdout.write(_deny_output(decision) + "\n")
    return 0


def _closed(payload: dict[str, Any], reason: str) -> int:
    """Deniega sin decision evaluada. Sale con 2: Claude Code bloquea pase lo que pase."""
    decision = Decision("deny", R_CLOSED, reason)
    try:
        record(payload, decision)
    except Exception:  # sin audit log se deniega igual: el lado seguro
        reason += "; tampoco se pudo registrar"
    sys.stdout.write(_deny_output(decision) + "\n")
    sys.stderr.write(f"politica: {reason}\n")
    return 2


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        return run(_read_stdin())
    except Exception as exc:  # fallo cerrado hasta en la lectura de la entrada
        sys.stderr.write(f"politica: fallo cerrado ({type(exc).__name__}: {exc})\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
