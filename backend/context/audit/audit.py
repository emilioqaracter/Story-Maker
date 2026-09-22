"""`context.audit`. Auditoria del paquete antes de gastar la llamada.

RF-35, RF-36, RF-37, RF-80. Corre **antes** de llamar al modelo, y esa es toda
su razon de ser: arbitrar antes de generar es mucho mas barato que reparar
despues.

Una comprobacion se porta distinto que las demas y conviene verlo: que la pierna
semantica se haya ejecutado **no** es una comprobacion de verdad, asi que no
aplica el fallo cerrado. Se marca el paquete como degradado, se traza y se
sigue. Recuperar peor una vez no es lo mismo que generar sobre un hecho falso.
"""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from commons.types.primitives import BlockProvenance
from context.packing.packet import Packet, Priority


class AuditFinding(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: str
    detail: str
    blocking: bool = Field(
        description="Si impide generar. Lo no bloqueante se marca y se traza"
    )


class AuditReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    findings: tuple[AuditFinding, ...] = Field(default_factory=tuple)

    @property
    def blocks_generation(self) -> bool:
        return any(f.blocking for f in self.findings)

    @property
    def conflict(self) -> bool:
        """Hay dos versiones del mismo hecho: va al Arbitro antes de generar."""
        return any(f.kind == "conflicto-de-hechos" for f in self.findings)


def audit(
    packet: Packet,
    *,
    active_cast: Sequence[str],
    budget: int,
    facts: Sequence[tuple[str, str]] = (),
) -> AuditReport:
    """Comprueba el paquete. `facts` son pares (clave, valor) ya extraidos.

    `facts` entra como argumento en vez de extraerse aqui porque extraerlo
    exigiria entender el contenido de cada bloque, y esta funcion tiene que
    poder comprobarse sin montar media novela.
    """
    findings: list[AuditFinding] = []
    findings += _check_conflicts(facts)
    findings += _check_cast(packet, active_cast)
    findings += _check_anchors(packet)
    findings += _check_budget(packet, budget)
    findings += _check_provenance(packet)
    findings += _check_working_memory(packet)
    if packet.degraded:
        findings.append(
            AuditFinding(
                kind="recuperacion-degradada",
                detail="la pierna semantica no aporto; el paquete va con una sola pierna",
                blocking=False,
            )
        )
    return AuditReport(findings=tuple(findings))


def _check_conflicts(facts: Sequence[tuple[str, str]]) -> list[AuditFinding]:
    """CTX-15. Dos versiones del mismo hecho.

    **Bloquea**: no se genera. Va al Arbitro, se incorpora la vigente y se
    vuelve a auditar. Generar sobre un paquete contradictorio produce prosa que
    habra que reparar, y reparar cuesta mas que arbitrar.
    """
    por_clave: dict[str, set[str]] = {}
    for clave, valor in facts:
        por_clave.setdefault(clave, set()).add(valor)

    return [
        AuditFinding(
            kind="conflicto-de-hechos",
            detail=f"{clave!r} aparece con {len(valores)} valores: {sorted(valores)}",
            blocking=True,
        )
        for clave, valores in sorted(por_clave.items())
        if len(valores) > 1
    ]


def _check_cast(packet: Packet, active_cast: Sequence[str]) -> list[AuditFinding]:
    """Todo el elenco activo tiene ficha.

    Si falta una entidad, es un defecto de planificacion y no del paquete: la
    especificacion pidio a alguien que no existe en el canon.
    """
    presentes = " ".join(b.content for b in packet.blocks)
    faltan = [e for e in active_cast if e not in presentes]
    return [
        AuditFinding(
            kind="elenco-sin-ficha",
            detail=f"sin ficha en el paquete: {faltan}",
            blocking=True,
        )
    ] if faltan else []


def _check_anchors(packet: Packet) -> list[AuditFinding]:
    """Las anclas estan y no vienen vacias. Una llamada sin ellas es deriva
    garantizada."""
    ancla = next((b for b in packet.blocks if b.name == "ancla"), None)
    if ancla is None or not ancla.content.strip():
        return [
            AuditFinding(
                kind="sin-ancla",
                detail="el paquete no lleva ancla de estilo e invariantes",
                blocking=True,
            )
        ]
    return []


def _check_budget(packet: Packet, budget: int) -> list[AuditFinding]:
    if packet.tokens > budget:
        return [
            AuditFinding(
                kind="fuera-de-presupuesto",
                detail=f"{packet.tokens} tokens sobre un presupuesto de {budget}",
                blocking=True,
            )
        ]
    return []


def _check_provenance(packet: Packet) -> list[AuditFinding]:
    """Cada fragmento con su cupo y su procedencia; un fragmento sin motivo se
    descarta (RF-80). Y la prosa congelada dice de que capitulo viene."""
    out: list[AuditFinding] = []
    for block in packet.blocks:
        if block.priority is Priority.RETRIEVED and block.tokens and block.quota is None:
            out.append(
                AuditFinding(
                    kind="fragmento-sin-motivo",
                    detail=f"{block.name!r} viene sin cupo: no se puede justificar por que entro",
                    blocking=True,
                )
            )
        if (
            block.provenance is BlockProvenance.FROZEN_PROSE
            and block.tokens
            and block.source_chapter is None
        ):
            out.append(
                AuditFinding(
                    kind="prosa-sin-capitulo",
                    detail=f"{block.name!r} es prosa congelada y no dice de que capitulo",
                    blocking=True,
                )
            )
    return out


def _check_working_memory(packet: Packet) -> list[AuditFinding]:
    """RF-37. La memoria de trabajo nunca entra en un paquete.

    Si un borrador rechazado llegara al Escritor, el sistema estaria aprendiendo
    de su propio error. Se detecta por procedencia: un bloque de prosa que no es
    congelada ni canon ni plan no tiene de donde salir.
    """
    return [
        AuditFinding(
            kind="memoria-de-trabajo-en-paquete",
            detail=f"{b.name!r} trae material sin procedencia valida",
            blocking=True,
        )
        for b in packet.blocks
        if b.provenance not in set(BlockProvenance)
    ]
