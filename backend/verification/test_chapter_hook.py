"""El hook `PostToolUse` de capitulo. `specs/srs-backend-v4.md` RF-251, RI-66, RNF-56. VER-05.

Se prueba como lo lanza Claude Code: un proceso aparte con el JSON del hook por
la entrada estandar, y se mira el codigo de salida y la salida de error.
"""

from __future__ import annotations

import json
import os
import shutil

# Las pruebas lanzan el hook del repositorio con argumentos fijos.
import subprocess  # nosec B404
import sys
from collections.abc import Sequence
from pathlib import Path

from canon.brief import Brief, BriefEntity, create_novel
from canon.db import connection
from canon.freeze.freeze import SceneToFreeze, commit_chapter, prepare
from commons.provider.port import Embedding
from commons.types.primitives import WorldTime

REPO = Path(__file__).resolve().parents[2]
HOOK = REPO / ".claude" / "hooks" / "chapter_gate.py"

PRESENTE = (
    "Marcos entra en el vestuario. Mira a sus compañeros. Nadie habla. "
    "Coge la camiseta y sale al campo. El estadio ruge.\n"
)
PASADO = (
    "Marcos entró en el vestuario. Miró a sus compañeros. Nadie habló. "
    "Cogió la camiseta y salió al campo. El estadio rugía.\n"
)


def _hook(payload: object, *args: str, script: Path = HOOK) -> subprocess.CompletedProcess[bytes]:
    entrada = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
    # Ruta y argumentos fijos de la prueba; no entra nada del exterior.
    return subprocess.run(  # nosec B603
        [sys.executable, str(script), *args],
        input=entrada,
        capture_output=True,
        timeout=60,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )


def _write(path: Path) -> dict[str, object]:
    return {
        "hook_event_name": "PostToolUse",
        "tool_name": "Write",
        "tool_input": {"file_path": str(path), "content": path.read_text(encoding="utf-8")},
        "tool_response": {"success": True},
    }


def _err(r: subprocess.CompletedProcess[bytes]) -> str:
    return r.stderr.decode("utf-8")


def test_un_capitulo_en_presente_se_bloquea_con_el_defecto(tmp_path: Path) -> None:
    """La puerta de T45: codigo 2 y el defecto con su cita en la salida de error."""
    capitulo = tmp_path / "uno.chapter.md"
    capitulo.write_text(PRESENTE, encoding="utf-8")
    r = _hook(_write(capitulo))
    assert r.returncode == 2
    assert "check.format" in _err(r)
    assert "presente" in _err(r)
    assert "«entra»" in _err(r)
    assert "S1" in _err(r)


def test_un_capitulo_en_pasado_pasa(tmp_path: Path) -> None:
    capitulo = tmp_path / "uno.chapter.txt"
    capitulo.write_text(PASADO, encoding="utf-8")
    r = _hook(_write(capitulo))
    assert r.returncode == 0, _err(r)


def test_lo_que_no_es_capitulo_no_se_mira(tmp_path: Path) -> None:
    otro = tmp_path / "notas.md"
    otro.write_text(PRESENTE, encoding="utf-8")
    assert _hook(_write(otro)).returncode == 0


def test_una_ruta_relativa_se_resuelve_contra_cwd_y_multiedit_cuenta(tmp_path: Path) -> None:
    (tmp_path / "dos.chapter.md").write_text(PRESENTE, encoding="utf-8")
    payload = {
        "cwd": str(tmp_path),
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": "dos.chapter.md",
            "edits": [{"old_string": "a", "new_string": "b"}],
        },
    }
    r = _hook(payload)
    assert r.returncode == 2
    assert "dos.chapter.md" in _err(r)


def test_una_fecha_sin_calendario_cuenta_como_fallo(tmp_path: Path) -> None:
    """Sin novela, listas vacias (RF-251): la fecha no se puede contrastar."""
    capitulo = tmp_path / "tres.chapter.md"
    capitulo.write_text("Marcos llegó el 3 de marzo al estadio.\n", encoding="utf-8")
    r = _hook(_write(capitulo))
    assert r.returncode == 2
    assert "check.timeline" in _err(r)


# ------------------------------------------------ con el canon de una novela


class _Embedder:
    def embed(self, texts: Sequence[str], *, is_query: bool) -> list[Embedding]:
        return [Embedding(values=(0.1, 0.2), model_id="doble", dimension=2) for _ in texts]


def _novela(tmp_path: Path, textos: Sequence[str]) -> Path:
    path = tmp_path / "n.sqlite"
    brief = Brief(
        title="Prueba",
        start=WorldTime(stamp="2026-08-01"),
        entities=(
            BriefEntity(id="marcos", kind="person", name="Marcos"),
            BriefEntity(id="campo", kind="place", name="el campo"),
        ),
        style_guide="Tercera persona, pasado.",
        target_words=2000,
    )
    create_novel(path, brief, global_terms=("linimento",))
    escenas = [
        SceneToFreeze(
            id=f"c1e{n}",
            chapter=1,
            scene_number=n,
            pov_entity="marcos",
            place_entity="campo",
            world_time=WorldTime(stamp=f"2026-08-1{n}"),
            function="establecer",
            text=texto,
            summary=f"resumen {n}",
            present=("marcos",),
        )
        for n, texto in enumerate(textos, start=1)
    ]
    prep = prepare(escenas, chapter=1, chapter_summary="cap 1", embed=_Embedder())
    with connection.canon_writer(path) as con:
        commit_chapter(con, prep)
    return path


def test_modo_manual_con_el_canon_de_la_novela(tmp_path: Path) -> None:
    """`--novel --chapter`: la prohibida global del canon es un S1 de check.forbidden."""
    sucia = _novela(tmp_path / "a", ["Marcos se frotó el linimento.", "Marcos salió al campo."])
    r = _hook(b"", "--novel", str(sucia), "--chapter", "1")
    assert r.returncode == 2
    assert "check.forbidden" in _err(r)
    assert "«linimento»" in _err(r)

    limpia = _novela(tmp_path / "b", ["Marcos se ató las botas.", "Marcos salió al campo."])
    assert _hook(b"", "--novel", str(limpia), "--chapter", "1").returncode == 0
    assert _hook(b"", "--novel", str(limpia), "--chapter", "9").returncode == 2


def test_un_fichero_con_el_canon_de_una_novela(tmp_path: Path) -> None:
    novela = _novela(tmp_path, ["Marcos salió al campo."])
    borrador = tmp_path / "b.chapter.md"
    borrador.write_text("Marcos olió el linimento del vestuario.\n", encoding="utf-8")
    r = _hook(b"", "--novel", str(novela), "--file", str(borrador))
    assert r.returncode == 2
    assert "check.forbidden" in _err(r)


# ------------------------------------------------------ fallo cerrado · RNF-56


def test_una_entrada_ilegible_bloquea(tmp_path: Path) -> None:
    assert _hook(b"{no es json").returncode == 2
    falta = {"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "x.chapter.md")}}
    r = _hook(falta)
    assert r.returncode == 2
    assert "no se pudo validar" in _err(r)


def test_sin_backend_importable_bloquea(tmp_path: Path) -> None:
    """Copiado fuera del repositorio no encuentra `backend/`: sale con 2, no con 0."""
    aislado = tmp_path / "x" / ".claude" / "hooks" / "chapter_gate.py"
    aislado.parent.mkdir(parents=True)
    shutil.copy(HOOK, aislado)
    capitulo = tmp_path / "uno.chapter.md"
    capitulo.write_text(PASADO, encoding="utf-8")
    r = _hook(_write(capitulo), script=aislado)
    assert r.returncode == 2
    assert "ModuleNotFoundError" in _err(r)


def test_llama_a_los_validadores_reales_sin_copiarlos() -> None:
    """RF-251. El hook importa los verificadores del motor y no define ninguno."""
    fuente = HOOK.read_text(encoding="utf-8")
    assert "from verification.checks import deterministic" in fuente
    assert "from verification.checks import forbidden" in fuente
    assert "from verification import gates" in fuente
    assert "def check_" not in fuente
