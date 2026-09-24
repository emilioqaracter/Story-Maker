"""Publicar en Langfuse los prompts del repositorio. RI-68, RF-266, D-86.

`python -m orchestration.prompts_sync [--dry-run]`

**El repositorio es la fuente; Langfuse, el registro.** Cada agente es un prompt
de Langfuse con su nombre, y cada `prompt_version` (RI-34), una version con esa
etiqueta. Es la misma etiqueta que lleva cada generation del espejo, asi que
Langfuse puede decir que version de prompt produjo que resultado.

Tres reglas, y las tres salen de la misma idea:

- **Publicar dos veces sin cambios no crea version.** La etiqueta es el hash del
  texto: si Langfuse ya tiene una version con ella, el texto es el mismo.
- **Cambiar un byte si crea version**, porque cambia el hash.
- **La tirada nunca lee de aqui.** Pedir el prompt a Langfuse en cada llamada
  meteria la red en el ciclo (D-86). Este modulo solo lo usa quien publica, a
  mano o en la ola de tiradas reales, nunca el motor.

Lo que se publica es lo que se hashea (`engine.prompt_sources`): una sola lista
para las dos cosas, o la etiqueta dejaria de nombrar el texto.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict

from orchestration import engine


class Prompt(BaseModel):
    """Un prompt del repositorio tal como se publica."""

    model_config = ConfigDict(frozen=True)

    name: str
    label: str
    text: str


def agents() -> list[str]:
    """Los agentes con prompt: los doce del motor y los dos del entrevistador."""
    return sorted({*engine.PROMPT_MODULES, *engine.INTERVIEWER_MODULES})


def render(agent: str) -> str:
    """El texto publicado: cada parte con su origen, en el orden en que se hashea."""
    return "\n\n".join(
        f"# {origen}\n\n{contenido.decode('utf-8')}"
        for origen, contenido in engine.prompt_sources(agent)
    )


def repository_prompts() -> list[Prompt]:
    """RF-266. Todos los prompts del repositorio, con su `prompt_version` como etiqueta."""
    return [Prompt(name=a, label=engine.prompt_version(a), text=render(a)) for a in agents()]


class PromptStore(Protocol):
    """Lo unico que la publicacion necesita de Langfuse."""

    def has_label(self, name: str, label: str) -> bool: ...

    def create(self, name: str, text: str, label: str) -> None: ...


class SyncReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    created: tuple[str, ...]
    unchanged: tuple[str, ...]


def sync(store: PromptStore, prompts: Sequence[Prompt] | None = None) -> SyncReport:
    """Publica lo que Langfuse no tiene. Idempotente: la etiqueta es el hash del texto."""
    creados: list[str] = []
    iguales: list[str] = []
    for p in repository_prompts() if prompts is None else prompts:
        if store.has_label(p.name, p.label):
            iguales.append(p.name)
            continue
        store.create(p.name, p.text, p.label)
        creados.append(p.name)
    return SyncReport(created=tuple(creados), unchanged=tuple(iguales))


class LangfusePromptStore:
    """`PromptStore` sobre el SDK de Langfuse. Solo lo construye `main`."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def has_label(self, name: str, label: str) -> bool:
        from langfuse.api import NotFoundError

        try:
            self._client.api.prompts.get(name, label=label)
        except NotFoundError:
            return False
        return True

    def create(self, name: str, text: str, label: str) -> None:
        self._client.create_prompt(
            name=name,
            prompt=text,
            labels=[label],
            type="text",
            commit_message=f"prompt_version {label}",
        )


def main(argv: list[str] | None = None) -> int:
    """RI-68. Publica los prompts; con `--dry-run`, solo dice que publicaria."""
    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    prompts = repository_prompts()
    if args.dry_run:
        print(json.dumps({p.name: p.label for p in prompts}, ensure_ascii=False, indent=1))
        return 0

    from commons.tracing.langfuse_export import config_from_env, library_available, missing_keys

    config = config_from_env()
    if config is None:
        sys.stderr.write(f"prompts.disabled: faltan {', '.join(missing_keys())}\n")
        return 2
    if not library_available():
        sys.stderr.write("prompts.disabled: falta la libreria langfuse\n")
        return 2
    try:
        from langfuse import Langfuse

        cliente = Langfuse(
            public_key=config.public_key,
            secret_key=config.secret_key,
            base_url=config.base_url,
            tracing_enabled=False,
        )
        informe = sync(LangfusePromptStore(cliente), prompts)
    except Exception as exc:
        motivo = f"{type(exc).__name__}: {exc}"
        for secreto in config.secrets:
            motivo = motivo.replace(secreto, "[CLAVE_OCULTA]")
        sys.stderr.write(f"prompts.failed: {motivo[:300]}\n")
        return 1
    print(json.dumps(informe.model_dump(), ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
