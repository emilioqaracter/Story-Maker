"""`style.fingerprint`. La huella estilistica de un capitulo (POE-13).

RF-137, D-40, RNF-33. Cinco metricas, las de `architecture.md` §4.6:

- longitud media de frase, en palabras;
- varianza de esa longitud;
- ratio adjetivo/sustantivo, con el etiquetado morfologico de spaCy;
- los n-gramas de 4 mas frecuentes;
- riqueza lexica, como razon tipo/token sobre ventanas fijas.

**Determinista**: el mismo texto da la misma huella. spaCy con un modelo fijo
lo es, y la riqueza se mide por ventanas de tamano fijo porque la razon
tipo/token cruda depende de la longitud del texto y dos capitulos de largo
distinto no serian comparables.

El modelo `es_core_news_sm` viaja en la imagen (RNF-33): si no carga, la huella
no se puede calcular y la comprobacion cuenta como fallida, no como pasada.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter
from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

#: D-40.
SPACY_MODEL = "es_core_news_sm"
#: Ventana de la razon tipo/token. Fija para que capitulos de largo distinto
#: se puedan comparar: es la convencion de la MSTTR, no un umbral.
RICHNESS_WINDOW = 100
TOP_NGRAMS = 10

_SENTENCE = re.compile(r"[^.!?…]+[.!?…]*")
_WORD = re.compile(r"\w+", re.UNICODE)


class FingerprintUnavailableError(RuntimeError):
    """El modelo morfologico no carga. Fallo cerrado."""


class Fingerprint(BaseModel):
    model_config = ConfigDict(frozen=True)

    mean_sentence_len: float = Field(ge=0.0)
    var_sentence_len: float = Field(ge=0.0)
    adj_noun_ratio: float = Field(ge=0.0)
    top_ngrams: tuple[str, ...]
    lexical_richness: float = Field(ge=0.0, le=1.0)

    def vector(self) -> dict[str, float]:
        """Las metricas numericas, que son las que se comparan en desviaciones."""
        return {
            "mean_sentence_len": self.mean_sentence_len,
            "var_sentence_len": self.var_sentence_len,
            "adj_noun_ratio": self.adj_noun_ratio,
            "lexical_richness": self.lexical_richness,
        }


@lru_cache(maxsize=1)
def _nlp() -> Any:
    try:
        import spacy
    except ImportError as exc:  # pragma: no cover - la imagen lo trae
        raise FingerprintUnavailableError("spaCy no esta instalado") from exc
    try:
        return spacy.load(SPACY_MODEL, disable=["parser", "ner", "lemmatizer"])
    except OSError as exc:  # pragma: no cover - la imagen lo trae
        raise FingerprintUnavailableError(f"no carga el modelo {SPACY_MODEL}") from exc


def _sentence_lengths(text: str) -> list[int]:
    return [n for s in _SENTENCE.findall(text) if (n := len(_WORD.findall(s))) > 0]


def _richness(words: list[str]) -> float:
    if not words:
        return 0.0
    if len(words) < RICHNESS_WINDOW:
        return len(set(words)) / len(words)
    ventanas = [
        words[i : i + RICHNESS_WINDOW]
        for i in range(0, len(words) - RICHNESS_WINDOW + 1, RICHNESS_WINDOW)
    ]
    return statistics.fmean(len(set(v)) / len(v) for v in ventanas)


def compute(text: str) -> Fingerprint:
    longitudes = _sentence_lengths(text)
    palabras = [w.lower() for w in _WORD.findall(text)]
    doc = _nlp()(text)
    adjetivos = sum(1 for t in doc if t.pos_ == "ADJ")
    sustantivos = sum(1 for t in doc if t.pos_ in ("NOUN", "PROPN"))
    ngramas = Counter(" ".join(palabras[i : i + 4]) for i in range(len(palabras) - 3))
    top = tuple(g for g, _ in sorted(ngramas.items(), key=lambda kv: (-kv[1], kv[0]))[:TOP_NGRAMS])
    return Fingerprint(
        mean_sentence_len=statistics.fmean(longitudes) if longitudes else 0.0,
        var_sentence_len=statistics.pvariance(longitudes) if len(longitudes) > 1 else 0.0,
        adj_noun_ratio=(adjetivos / sustantivos) if sustantivos else 0.0,
        top_ngrams=top,
        lexical_richness=_richness(palabras),
    )
