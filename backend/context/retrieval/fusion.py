"""Fusion de las dos piernas por rangos.

RF-76, RF-77. Los resultados lexicos vienen con una puntuacion y los semanticos
con otra. **Son escalas incomparables**, y normalizarlas exige una calibracion
que cambia con el tamano del corpus, es decir, que cambia en cada capitulo.

Asi que no se usan las puntuaciones: se usan las **posiciones**. Cada fragmento
suma, por cada pierna en que aparece, uno partido por una constante mas su
posicion.

Tres cosas que esto compra y que la alternativa no:

- **No hay que calibrar nada.** Solo usa posiciones, asi que es estable capitulo
  a capitulo.
- **Es determinista.** El mismo canon y la misma peticion dan el mismo orden,
  que es lo que hace reproducible una tirada y comprobable una propiedad.
- **Se degrada sola.** Si una pierna devuelve vacio, la fusion sigue con la otra
  sin caso especial.
"""

from __future__ import annotations

from collections.abc import Sequence

#: Constante de la fusion reciproca de rangos. Viene del trabajo que introdujo
#: el metodo y **no se ha ajustado aqui**: ajustarla exige medir con el conjunto
#: dorado, que llega en un paso posterior. Queda como decision abierta.
RRF_K = 60


def reciprocal_rank_fusion(
    legs: Sequence[Sequence[str]], *, k: int = RRF_K
) -> list[tuple[str, float]]:
    """Fusiona varias listas ordenadas de identificadores.

    Cada lista viene ya ordenada de mejor a peor. Devuelve los identificadores
    con su puntuacion, de mayor a menor.

    El desempate es por identificador y no por orden de aparicion: con dos
    fragmentos de igual puntuacion, ordenar por como llegaron haria que el
    resultado dependiera de en que orden corrieron las piernas, y las dos son
    independientes a proposito.
    """
    scores: dict[str, float] = {}
    for leg in legs:
        for position, chunk_id in enumerate(leg):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + position + 1)

    return sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
