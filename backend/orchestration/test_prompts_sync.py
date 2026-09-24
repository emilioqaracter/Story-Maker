"""Publicar los prompts del repositorio en Langfuse. RI-68, RF-266, D-86.

Metodo VER-05, con un almacen doble que se comporta como Langfuse: una version
nueva por cada `create`, y una etiqueta que apunta a una sola version.
"""

from __future__ import annotations

import pytest

from orchestration import engine, prompts_sync
from orchestration.prompts_sync import Prompt, sync


class FakeStore:
    """Como Langfuse: cada `create` es una version; una etiqueta, en una sola."""

    def __init__(self) -> None:
        self.versions: dict[str, list[tuple[str, str]]] = {}

    def has_label(self, name: str, label: str) -> bool:
        return any(lab == label for lab, _t in self.versions.get(name, []))

    def create(self, name: str, text: str, label: str) -> None:
        self.versions.setdefault(name, []).append((label, text))


def test_publicar_dos_veces_sin_cambios_no_crea_version() -> None:
    """RF-266: la etiqueta es el hash del texto."""
    store = FakeStore()
    primera = sync(store)
    segunda = sync(store)
    assert set(primera.created) == set(prompts_sync.agents())
    assert segunda.created == ()
    assert set(segunda.unchanged) == set(prompts_sync.agents())
    assert all(len(v) == 1 for v in store.versions.values())


def test_cambiar_un_byte_crea_version(monkeypatch: pytest.MonkeyPatch) -> None:
    store = FakeStore()
    sync(store)
    fuentes = engine.prompt_sources

    def con_un_byte_mas(agent: str) -> list[tuple[str, bytes]]:
        partes = fuentes(agent)
        if agent == "escritor":
            origen, contenido = partes[-1]
            partes[-1] = (origen, contenido + b" ")
        return partes

    monkeypatch.setattr(engine, "prompt_sources", con_un_byte_mas)
    informe = sync(store)
    assert informe.created == ("escritor",)
    etiquetas = [lab for lab, _t in store.versions["escritor"]]
    assert len(etiquetas) == 2 and etiquetas[1] == engine.prompt_version("escritor")


def test_la_etiqueta_es_la_prompt_version_de_la_tirada() -> None:
    """RF-266: la misma etiqueta que lleva cada generation del espejo."""
    for p in prompts_sync.repository_prompts():
        assert p.label == engine.prompt_version(p.name)
        # Lo publicado lleva cada fichero que entra en el hash, con su origen.
        for origen, _contenido in engine.prompt_sources(p.name):
            assert f"# {origen}" in p.text


def test_los_dos_agentes_del_entrevistador_tienen_prompt_publicado() -> None:
    from brief import extract, interpret

    publicados = {p.name: p.label for p in prompts_sync.repository_prompts()}
    assert publicados["brief.extract"] == extract.prompt_version()
    assert publicados["amend.interpret"] == extract.prompt_version(interpret.__file__)


def test_sync_acepta_una_lista_propia() -> None:
    store = FakeStore()
    informe = sync(store, [Prompt(name="escritor", label="abc", text="x")])
    assert informe.created == ("escritor",)


def test_sin_claves_no_publica_nada(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """RI-60 aplicado a RI-68: nombra lo que falta, nunca un valor."""
    for k in ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_BASE_URL"):
        monkeypatch.delenv(k, raising=False)
    assert prompts_sync.main([]) == 2
    assert "LANGFUSE_SECRET_KEY" in capsys.readouterr().err


def test_en_seco_dice_que_publicaria(capsys: pytest.CaptureFixture[str]) -> None:
    assert prompts_sync.main(["--dry-run"]) == 0
    assert "escritor" in capsys.readouterr().out


def test_la_tirada_no_importa_la_publicacion() -> None:
    """D-86: el motor nunca lee prompts de Langfuse; este modulo no esta en su camino."""
    import ast
    from pathlib import Path

    raiz = Path(engine.__file__).resolve().parent
    for nombre in ("engine.py", "loop.py", "compose.py", "dispatch.py"):
        arbol = ast.parse((raiz / nombre).read_text(encoding="utf-8"))
        importados = {
            n.module
            for n in ast.walk(arbol)
            if isinstance(n, ast.ImportFrom) and n.module is not None
        } | {a.name for n in ast.walk(arbol) if isinstance(n, ast.Import) for a in n.names}
        assert "orchestration.prompts_sync" not in importados, nombre
        assert not any(m.startswith("langfuse") for m in importados), nombre
