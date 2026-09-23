"""Referencia, desviacion y deriva de la huella (CTX-12).

RF-138, RF-142, D-42. La referencia es la huella de los **tres primeros
capitulos congelados**. La desviacion de un capitulo es, por metrica, cuantas
desviaciones tipicas de la referencia se aparta. **Deriva** es mas de 2
desviaciones tipicas en alguna metrica, **sostenida tres capitulos**: un
capitulo atipico a proposito no dispara nada, tres seguidos si.

Con tres capitulos de referencia la desviacion tipica puede salir cero --tres
capitulos identicos en una metrica--. Entonces se usa un suelo del 5 % de la
media, para que cualquier variacion minima no cuente como infinitas
desviaciones. Es una lectura necesaria de D-42, declarada, no un umbral nuevo
de calidad.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from verification.style.fingerprint import Fingerprint

#: D-42.
REFERENCE_CHAPTERS = 3
DRIFT_SIGMAS = 2.0
SUSTAINED = 3
#: D-69. Suelo de la desviacion tipica, como fraccion de la media (ver arriba).
SIGMA_FLOOR = 0.05


class Reference(BaseModel):
    model_config = ConfigDict(frozen=True)

    mean: dict[str, float]
    sigma: dict[str, float]


class Deviation(BaseModel):
    model_config = ConfigDict(frozen=True)

    per_metric: dict[str, float] = Field(description="En desviaciones tipicas, con signo")

    @property
    def max_abs(self) -> float:
        return max((abs(v) for v in self.per_metric.values()), default=0.0)

    @property
    def out_of_tolerance(self) -> bool:
        return self.max_abs > DRIFT_SIGMAS


def reference(fingerprints: Sequence[Fingerprint]) -> Reference | None:
    """La referencia, o `None` mientras no haya tres capitulos."""
    if len(fingerprints) < REFERENCE_CHAPTERS:
        return None
    base = fingerprints[:REFERENCE_CHAPTERS]
    claves = base[0].vector().keys()
    media = {k: statistics.fmean(f.vector()[k] for f in base) for k in claves}
    sigma = {
        k: max(statistics.pstdev([f.vector()[k] for f in base]), abs(media[k]) * SIGMA_FLOOR, 1e-9)
        for k in claves
    }
    return Reference(mean=media, sigma=sigma)


def deviation(fp: Fingerprint, ref: Reference) -> Deviation:
    return Deviation(
        per_metric={k: (v - ref.mean[k]) / ref.sigma[k] for k, v in fp.vector().items()}
    )


def sustained_drift(deviations: Sequence[Deviation]) -> bool:
    """RF-138. Fuera de tolerancia en los ultimos tres capitulos seguidos."""
    if len(deviations) < SUSTAINED:
        return False
    return all(d.out_of_tolerance for d in deviations[-SUSTAINED:])
