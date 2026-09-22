"""Presupuesto de reintentos y cuarentena.

RF-18, RF-19, RF-107, CAL-12, CAL-13. `architecture.md` §7.3.

**La escalera tiene tres peldanos, y cada uno no reintenta lo mismo otra vez:
sube un nivel y cambia el diagnostico.**

| Peldano | Intentos | Que asume |
|---|---|---|
| Escena | 3 | "la prosa esta mal" |
| Capitulo | 2 | "el encargo estaba mal" |
| Tramo | 1 | "el plan del tramo estaba mal" |

Agotado el tercero se recalcula el arco entero. No hay cuarto nivel: si un arco
falla dos veces, el problema esta en la escaleta y seguir reparando prosa es
perder tiempo.

**La cuarentena significa cosas distintas segun el nivel** (D-26), y esta es la
parte que parece razonable al reves:

- **Escena**: se rehace en su sitio con una especificacion mas estricta.
- **Capitulo**: se rehace de inmediato y **no se salta al siguiente**.

Escribir el capitulo N+1 exige del N su prosa literal --que ocupa un bloque no
compactable del paquete-- y su estado del mundo, que solo existe tras congelar.
Si el N esta cuarentenado no hay ni una ni otra, asi que el N+1 se escribiria
como si el N no hubiera ocurrido, y cuando el N se rehiciera lo haria contra un
canon donde el N+1 ya esta congelado ignorandolo. Eso no es continuar la
produccion: es fabricar una contradiccion que ninguna puerta detecta.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

#: RF-18. Los tres peldanos.
SCENE_ATTEMPTS = 3
CHAPTER_ATTEMPTS = 2
ARC_REPLANS = 1


class Level(StrEnum):
    SCENE = "escena"
    CHAPTER = "capitulo"
    ARC = "arco"


class Action(StrEnum):
    """Que hacer tras un fallo."""

    RETRY = "reintentar"
    QUARANTINE_AND_RESPEC = "cuarentena-y-especificacion-mas-estricta"
    QUARANTINE_AND_REPLAN = "cuarentena-y-replanificar-tramo"
    RECOMPUTE_ARC = "recalcular-arco"


class Budget(BaseModel):
    """Lo consumido en cada nivel para un capitulo."""

    model_config = ConfigDict(frozen=True)

    scene_attempts: int = Field(default=0, ge=0)
    chapter_attempts: int = Field(default=0, ge=0)
    arc_replans: int = Field(default=0, ge=0)


class Decision(BaseModel):
    model_config = ConfigDict(frozen=True)

    action: Action
    level: Level
    budget: Budget
    reason: str


def on_failure(budget: Budget, *, level: Level) -> Decision:
    """Que hacer tras un fallo en `level`, dado lo ya consumido.

    Devuelve tambien el presupuesto actualizado, para que quien llame no tenga
    que acordarse de incrementarlo: olvidarse es como se fabrica un bucle
    infinito de reparacion.
    """
    if level is Level.SCENE:
        usado = budget.scene_attempts + 1
        if usado < SCENE_ATTEMPTS:
            return Decision(
                action=Action.RETRY,
                level=level,
                budget=budget.model_copy(update={"scene_attempts": usado}),
                reason=f"intento {usado} de {SCENE_ATTEMPTS} sobre la escena",
            )
        return Decision(
            action=Action.QUARANTINE_AND_RESPEC,
            level=level,
            # El contador de escena se reinicia: la escena que viene es otra,
            # con otra especificacion, y arrastrar los intentos de la anterior
            # le daria menos oportunidades de las que le tocan.
            budget=budget.model_copy(
                update={"scene_attempts": 0, "chapter_attempts": budget.chapter_attempts + 1}
            ),
            reason="agotados los intentos de escena: el problema no esta en la "
            "prosa sino en el encargo",
        )

    if level is Level.CHAPTER:
        usado = budget.chapter_attempts + 1
        if usado < CHAPTER_ATTEMPTS:
            return Decision(
                action=Action.QUARANTINE_AND_RESPEC,
                level=level,
                budget=budget.model_copy(update={"chapter_attempts": usado}),
                reason=f"intento {usado} de {CHAPTER_ATTEMPTS} sobre el capitulo",
            )
        return Decision(
            action=Action.QUARANTINE_AND_REPLAN,
            level=level,
            budget=budget.model_copy(
                update={"chapter_attempts": 0, "arc_replans": budget.arc_replans + 1}
            ),
            reason="agotados los intentos de capitulo: el problema esta en el tramo",
        )

    usado = budget.arc_replans + 1
    return Decision(
        action=Action.RECOMPUTE_ARC,
        level=Level.ARC,
        budget=budget.model_copy(update={"arc_replans": usado}),
        reason="no hay cuarto nivel: si un arco falla, el problema esta en la "
        "escaleta y seguir reparando prosa es perder tiempo",
    )


def may_start_chapter(*, previous_frozen: bool) -> bool:
    """RF-107. No se empieza un capitulo mientras el anterior no este congelado.

    Es la mitad practica de D-26: la cuarentena de capitulo no difiere nada, lo
    rehace. Sin esta comprobacion, "la produccion no se detiene" se leeria como
    "salta al siguiente", que fabrica una contradiccion invisible.
    """
    return previous_frozen
