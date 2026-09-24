"""ENT-59, RF-217, RF-218. `brief.extract` real sobre el texto libre del brief 02. VER-17.

    python -m evals.adversarial.real_02 evals/results/adversarial-02.json

Una sola llamada de modelo, por el mismo extractor que compone el servidor
(`orchestration.app._extractor`), dentro de un turno de la entrevista. No abre
ninguna tirada y no corre en `gate.py`: usa la suscripcion del CLI (RNF-58).
Guarda lo que devolvio el modelo, lo que se descarto y el borrador antes y
despues, que es lo que `evals/results/adversarial-02.md` lee.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from brief import interview
from brief.extract import Extraction, ModelExtractor, RawFact, prompt_version
from brief.interview import TurnIn
from orchestration.app import _extractor

TEXT = Path(__file__).resolve().parents[1] / "briefs" / "02-adversarial.texto-libre.txt"


def main(out: Path) -> dict[str, Any]:
    texto = TEXT.read_text(encoding="utf-8").strip()
    extractor = _extractor()
    assert isinstance(extractor, ModelExtractor)
    crudo: list[str] = []
    port = extractor._port
    original = port.complete_once

    def captura(*a: Any, **k: Any) -> Any:
        c = original(*a, **k)
        crudo.append(c.text)
        return c

    # El puerto es inmutable: se envuelve solo para guardar la respuesta cruda.
    object.__setattr__(port, "complete_once", captura)

    propuestos: list[dict[str, Any]] = []
    invalidos = [0]

    def espia(free_text: str, summary: str) -> Extraction | Sequence[RawFact]:
        salida = extractor(free_text, summary)
        propuestos.extend(f.model_dump(mode="json") for f in salida.facts)
        invalidos[0] = salida.invalid
        return salida

    estado = interview.turn(interview.new("adv-02"), TurnIn(answer="La cometa de Arenales"), None)
    antes = estado.draft.model_dump(mode="json")
    tras = interview.turn(estado, TurnIn(free_text=texto), espia)
    despues = tras.draft.model_dump(mode="json")
    llamada = extractor.calls[-1] if extractor.calls else {}
    claves = ("real_input", "output_tokens", "cost_usd", "duration_ms")
    registro: dict[str, Any] = {
        "fecha": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "prompt_version": prompt_version(),
        "modelo": llamada.get("model"),
        "tokens": {k: llamada.get(k) for k in claves},
        "llamada_ok": llamada.get("ok"),
        "error": llamada.get("error"),
        "texto_libre": texto,
        "respuesta_cruda_del_modelo": crudo[-1] if crudo else None,
        "propuestos_por_el_modelo": propuestos,
        "invalidos_por_esquema": invalidos[0],
        "propuestas_ancladas": [p.model_dump(mode="json") for p in tras.proposed],
        "citas_descartadas": tras.discarded_quotes,
        "descartados": [c for c in propuestos if c["quote"] not in texto],
        "notas": [m.text for m in tras.messages if m.kind == "note"],
        "borrador_igual_sin_aceptar": antes == despues,
        "brief_completo": tras.complete,
        "borrador_antes": antes,
        "borrador_despues": despues,
    }
    out.write_text(json.dumps(registro, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return registro


if __name__ == "__main__":
    r = main(Path(sys.argv[1]))
    resumen = ("prompt_version", "llamada_ok", "citas_descartadas", "borrador_igual_sin_aceptar")
    print(json.dumps({k: r[k] for k in resumen}, ensure_ascii=False))
