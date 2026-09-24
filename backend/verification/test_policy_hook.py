"""El hook `PreToolUse` de politica y su audit log.

`specs/srs-backend-v4.md` RF-252, RF-253, RI-66, RNF-56, D-92. VER-12 y VER-05.

Se prueba como lo lanza Claude Code: un proceso aparte con el JSON del hook por
la entrada estandar. `CLAUDE_PROJECT_DIR` apunta a un directorio temporal para
que el audit log de la prueba no se mezcle con el del repositorio. Ninguna
prueba abre un `.env`: las rutas son ficticias y la politica decide antes.
"""

from __future__ import annotations

import importlib.util
import json
import os

# Las pruebas lanzan el hook del repositorio con argumentos fijos.
import subprocess  # nosec B404
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from commons.tracing.trace import verify_chain
from verification.checks.forbidden import ForbiddenTerm

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / ".claude" / "hooks" / "policy.py"


def _hook(project: Path, payload: object) -> subprocess.CompletedProcess[bytes]:
    entrada = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    # Ruta y argumentos fijos de la prueba; no entra nada del exterior.
    return subprocess.run(  # nosec B603
        [sys.executable, str(HOOK)],
        input=entrada,
        capture_output=True,
        timeout=60,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)},
    )


def _audit(project: Path) -> list[dict[str, Any]]:
    path = project / ".claude" / "audit" / "policy.jsonl"
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def _decision(r: subprocess.CompletedProcess[bytes]) -> dict[str, Any]:
    salida: dict[str, Any] = json.loads(r.stdout.decode("utf-8"))["hookSpecificOutput"]
    return salida


def _read(path: str) -> dict[str, Any]:
    return {"hook_event_name": "PreToolUse", "tool_name": "Read", "tool_input": {"file_path": path}}


def _write(path: str, content: str = "x") -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": path, "content": content},
    }


def _bash(command: str) -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }


def test_leer_env_se_deniega_y_queda_en_el_audit_log(tmp_path: Path) -> None:
    """La puerta de T45: decision `deny` con motivo y un registro con regla e instante."""
    r = _hook(tmp_path, _read(str(tmp_path / ".env")))
    assert r.returncode == 0
    salida = _decision(r)
    assert salida["hookEventName"] == "PreToolUse"
    assert salida["permissionDecision"] == "deny"
    assert "secretos-no-se-leen" in salida["permissionDecisionReason"]

    (registro,) = _audit(tmp_path)
    assert registro["kind"] == "policy.decision"
    assert registro["fields"]["decision"] == "deny"
    assert registro["fields"]["rule"] == "secretos-no-se-leen"
    assert registro["fields"]["tool"] == "Read"
    assert registro["at"]
    assert registro["prev_hash"] == ""


@pytest.mark.parametrize(
    "ruta",
    [".env.local", "config/.env.production", "claves/servidor.pem", "home/.ssh/id_ed25519"],
)
def test_ficheros_de_claves_no_se_leen(tmp_path: Path, ruta: str) -> None:
    r = _hook(tmp_path, _read(str(tmp_path / ruta)))
    assert _decision(r)["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "ruta",
    [
        "backend/runs-real/n.sqlite",
        "backend/golden/v1-seed/n.sqlite",
        "backend/runs-x/n.sqlite-wal",
    ],
)
def test_escribir_el_canon_de_una_tirada_se_deniega(tmp_path: Path, ruta: str) -> None:
    r = _hook(tmp_path, _write(str(tmp_path / ruta)))
    salida = _decision(r)
    assert salida["permissionDecision"] == "deny"
    assert "canon-solo-lo-escribe-la-congelacion" in salida["permissionDecisionReason"]
    assert _audit(tmp_path)[-1]["fields"]["rule"] == "canon-solo-lo-escribe-la-congelacion"


@pytest.mark.parametrize(
    "comando",
    [
        "cat .env",
        "type backend\\.env",
        "grep KEY ../.env.local",
        'sqlite3 backend/runs-real/n.sqlite "DELETE FROM event"',
        "cp otra.sqlite backend/golden/v1-seed/n.sqlite",
        "echo x > backend/runs-a/n.sqlite",
    ],
)
def test_comandos_que_leen_secretos_o_escriben_canon_se_deniegan(
    tmp_path: Path, comando: str
) -> None:
    assert _decision(_hook(tmp_path, _bash(comando)))["permissionDecision"] == "deny"


@pytest.mark.parametrize(
    "comando",
    [
        "python -m pytest -q",
        "python -m venv .venv",
        'sqlite3 -readonly backend/runs-real/n.sqlite "SELECT count(*) FROM event"',
        'node -e "console.log(process.env.HOME)"',
    ],
)
def test_lo_demas_no_se_deniega_y_tambien_se_registra(tmp_path: Path, comando: str) -> None:
    """Regla 4. Sin decision para Claude Code --sigue su flujo de permisos-- y con registro."""
    r = _hook(tmp_path, _bash(comando))
    assert r.returncode == 0
    assert r.stdout.strip() == b""
    (registro,) = _audit(tmp_path)
    assert registro["fields"]["decision"] == "allow"
    assert registro["fields"]["rule"] == "por-defecto"


def test_la_primera_regla_que_casa_gana(tmp_path: Path) -> None:
    """Un comando que casa con la 1 y con la 2 se deniega por la 1."""
    r = _hook(tmp_path, _bash("cat .env > backend/runs-x/n.sqlite"))
    assert "canon-solo-lo-escribe-la-congelacion" in _decision(r)["permissionDecisionReason"]


def test_el_audit_log_no_guarda_contenido_ni_comandos(tmp_path: Path) -> None:
    _hook(tmp_path, _bash("export TOKEN=valor-que-no-debe-salir; cat .env"))
    _hook(tmp_path, _write(str(tmp_path / "a.md"), "contenido-que-no-debe-salir"))
    bruto = (tmp_path / ".claude" / "audit" / "policy.jsonl").read_text(encoding="utf-8")
    assert "valor-que-no-debe-salir" not in bruto
    assert "contenido-que-no-debe-salir" not in bruto


def test_cada_decision_encadena_y_borrar_una_se_detecta(tmp_path: Path) -> None:
    """RF-253. El audit log del hook lleva la misma cadena que la traza del motor."""
    for payload in (_read("a.py"), _read(".env"), _bash("ls"), _write("b.md")):
        _hook(tmp_path, payload)
    path = tmp_path / ".claude" / "audit" / "policy.jsonl"
    assert len(_audit(tmp_path)) == 4
    assert verify_chain(path) is None

    lineas = path.read_text(encoding="utf-8").splitlines()
    del lineas[1]
    path.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    assert verify_chain(path) == 2


# ------------------------------------------------------ fallo cerrado · RNF-56


def test_una_entrada_ilegible_se_deniega_con_codigo_2(tmp_path: Path) -> None:
    r = _hook(tmp_path, b"{no es json")
    assert r.returncode == 2
    assert _decision(r)["permissionDecision"] == "deny"
    assert _audit(tmp_path)[-1]["fields"]["rule"] == "fallo-cerrado"


def test_sin_audit_log_se_deniega(tmp_path: Path) -> None:
    """Si la decision no puede quedar escrita, no se permite nada."""
    ocupado = tmp_path / "proyecto"
    ocupado.write_text("un fichero donde deberia haber un directorio", encoding="utf-8")
    r = _hook(ocupado, _read("a.py"))
    assert r.returncode == 2
    assert _decision(r)["permissionDecision"] == "deny"


# ------------------------------------------- regla 3: prohibidas globales


def _policy() -> ModuleType:
    spec = importlib.util.spec_from_file_location("sm_policy_hook", HOOK)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    # Las dataclasses buscan su modulo en `sys.modules` al definirse.
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


def test_un_capitulo_con_una_prohibida_global_se_deniega() -> None:
    """Con `check.forbidden` del motor, sobre lo que se va a escribir."""
    policy = _policy()
    lista = (ForbiddenTerm(term="linimento", level="global"),)
    sucio = policy.decide(_write("n/uno.chapter.md", "Olía a Linimento."), terms=lista)
    assert (sucio.decision, sucio.rule) == ("deny", "capitulo-sin-prohibidas-globales")
    assert "Linimento" in sucio.reason

    edicion = {
        "tool_name": "Edit",
        "tool_input": {
            "file_path": "uno.chapter.txt",
            "old_string": "a",
            "new_string": "linimento",
        },
    }
    assert policy.decide(edicion, terms=lista).decision == "deny"
    limpio = policy.decide(_write("n/uno.chapter.md", "Olía a hierba."), terms=lista)
    assert limpio.decision == "allow"
    otro = policy.decide(_write("n/notas.md", "linimento"), terms=lista)
    assert otro.decision == "allow"


def test_la_regla_3_lee_la_lista_global_versionada(tmp_path: Path) -> None:
    """Sin sustituto, la lista es `canon/db/forbidden_global.txt` (RD-38)."""
    from canon.brief import read_global_forbidden

    terminos = read_global_forbidden()
    policy = _policy()
    assert tuple(t.term for t in policy.global_terms()) == terminos
    r = _hook(tmp_path, _write(str(tmp_path / "uno.chapter.md"), "Marcos salió al campo."))
    assert r.returncode == 0
    assert _audit(tmp_path)[-1]["fields"]["decision"] == "allow"


def test_hooks_a_la_vez_no_bifurcan_la_cadena(tmp_path: Path) -> None:
    """Claude Code puede lanzar varios hooks en paralelo: el cerrojo los turna."""
    entrada = json.dumps(_read("a.py")).encode("utf-8")
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
    procesos = [
        # Ruta y argumentos fijos de la prueba; no entra nada del exterior.
        subprocess.Popen(  # nosec B603
            [sys.executable, str(HOOK)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        for _ in range(6)
    ]
    for p in procesos:
        p.communicate(entrada, timeout=60)
        assert p.returncode == 0
    assert len(_audit(tmp_path)) == 6
    assert verify_chain(tmp_path / ".claude" / "audit" / "policy.jsonl") is None
