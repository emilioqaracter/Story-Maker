"""Ensamblaje, compactacion y auditoria del paquete.

RF-32 a RF-37, RF-103, RF-109. Metodos VER-05 y VER-06.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from commons.types.primitives import BlockProvenance, Quota
from context.audit.audit import audit
from context.packing.packet import Block, Packet, Priority, assemble, compact


def _b(name: str, tokens: int, priority: Priority, **kw: object) -> Block:
    base: dict[str, object] = {
        "name": name, "content": f"<{name}>", "tokens": tokens, "priority": priority,
        "provenance": BlockProvenance.CANON,
    }
    base.update(kw)
    return Block(**base)  # type: ignore[arg-type]


def _minimo() -> list[Block]:
    return [
        _b("ancla", 4_500, Priority.UNTOUCHABLE),
        _b("fichas", 1_600, Priority.SECONDARY_CARDS),
        _b("conocimiento", 600, Priority.UNTOUCHABLE),
        _b("especificacion", 900, Priority.UNTOUCHABLE),
    ]


# ------------------------------------------------------------------ el orden

def test_el_ancla_va_primera_y_la_especificacion_ultima() -> None:
    """RF-34. Aprovecha el sesgo de recencia en vez de sufrirlo."""
    p = assemble(agent="escritor", blocks=list(reversed(_minimo())))
    assert p.blocks[0].name == "ancla"
    assert p.blocks[-1].name == "especificacion"


def test_el_prefijo_cacheable_no_lleva_nada_voluble() -> None:
    """RF-103. El cache casa por prefijo: un byte distinto y se pierde la
    llamada entera, sin error."""
    p = assemble(agent="escritor", blocks=_minimo())
    assert p.cacheable_prefix == "<ancla>"
    assert "<especificacion>" in p.body()


# ------------------------------------------------------------ la compactacion

def test_se_sacrifica_primero_lo_recuperado() -> None:
    bloques = [
        *_minimo(),
        _b("frag", 3_000, Priority.RETRIEVED, quota=Quota.FREE),
        _b("prosa", 4_500, Priority.PREVIOUS_PROSE),
    ]
    # Suman 15.100. Con 12.500 basta con sacrificar los 3.000 de fragmentos
    # recuperados, que es el primer nivel; la prosa previa se queda.
    resultado = compact(bloques, budget=12_500)
    por_nombre = {b.name: b for b in resultado}
    assert por_nombre["frag"].compacted
    assert not por_nombre["prosa"].compacted


def test_las_anclas_no_se_tocan_jamas() -> None:
    """Una llamada sin ancla es deriva garantizada, y una sin especificacion no
    sabe que escribir."""
    resultado = compact(_minimo(), budget=100)
    intocables = {b.name for b in resultado if b.priority is Priority.UNTOUCHABLE}
    assert intocables == {"ancla", "conocimiento", "especificacion"}
    assert all(b.tokens > 0 for b in resultado if b.name in intocables)


def test_un_bloque_se_quita_entero_nunca_a_medias() -> None:
    """Medio bloque de fragmentos es peor que ninguno: el agente no sabe que le
    falta y se fia de lo que quedo."""
    bloques = [*_minimo(), _b("frag", 3_000, Priority.RETRIEVED, quota=Quota.FREE)]
    [frag] = [b for b in compact(bloques, budget=8_000) if b.name == "frag"]
    assert frag.tokens == 0
    assert frag.content == ""


@given(extra=st.integers(min_value=0, max_value=20_000))
def test_el_paquete_nunca_supera_su_presupuesto(extra: int) -> None:
    """La propiedad que importa: no hay entrada que produzca un paquete que se
    pase, salvo que lo intocable ya no quepa."""
    bloques = [*_minimo(), _b("frag", extra or 1, Priority.RETRIEVED, quota=Quota.FREE)]
    p = assemble(agent="escritor", blocks=bloques, budget=9_000)
    intocables = sum(b.tokens for b in bloques if b.priority is Priority.UNTOUCHABLE)
    assert p.tokens <= max(9_000, intocables)


def test_ensamblar_no_muta_lo_que_recibe() -> None:
    """RF-109. Es el aislamiento en forma comprobable: si dos llamadas
    compartieran un objeto de paquete, ya estaria roto aunque nadie lo notara."""
    bloques = [*_minimo(), _b("frag", 50_000, Priority.RETRIEVED, quota=Quota.FREE)]
    copia = [b.model_copy() for b in bloques]
    assemble(agent="escritor", blocks=bloques, budget=8_000)
    assert bloques == copia


# ------------------------------------------------------------------ auditoria

def _ok_packet() -> Packet:
    return assemble(agent="escritor", blocks=[
        Block(name="ancla", content="estilo e invariantes", tokens=4_500,
              priority=Priority.UNTOUCHABLE, provenance=BlockProvenance.CANON),
        Block(name="fichas", content="marcos elena", tokens=1_600,
              priority=Priority.SECONDARY_CARDS, provenance=BlockProvenance.CANON),
    ])


def test_un_paquete_sano_pasa() -> None:
    r = audit(_ok_packet(), active_cast=["marcos", "elena"], budget=20_000)
    assert not r.blocks_generation


def test_dos_versiones_del_mismo_hecho_bloquean() -> None:
    """CTX-15. Va al Arbitro antes de generar: arbitrar es mas barato que
    reparar prosa escrita sobre una contradiccion."""
    r = audit(_ok_packet(), active_cast=["marcos", "elena"], budget=20_000,
              facts=[("marcos.estado", "sano"), ("marcos.estado", "lesionado")])
    assert r.conflict and r.blocks_generation


def test_un_elenco_sin_ficha_bloquea() -> None:
    r = audit(_ok_packet(), active_cast=["fantasma"], budget=20_000)
    assert r.blocks_generation


def test_un_paquete_sin_ancla_bloquea() -> None:
    p = assemble(agent="escritor", blocks=[
        Block(name="fichas", content="marcos", tokens=10, priority=Priority.SECONDARY_CARDS,
              provenance=BlockProvenance.CANON)])
    assert audit(p, active_cast=["marcos"], budget=20_000).blocks_generation


def test_un_fragmento_sin_cupo_bloquea() -> None:
    """RF-80. Un fragmento sin motivo no se puede justificar, asi que se
    descarta."""
    p = assemble(agent="escritor", blocks=[
        Block(name="ancla", content="x", tokens=10, priority=Priority.UNTOUCHABLE,
              provenance=BlockProvenance.CANON),
        Block(name="frag", content="y", tokens=10, priority=Priority.RETRIEVED,
              provenance=BlockProvenance.FROZEN_PROSE, source_chapter=1),
    ])
    r = audit(p, active_cast=[], budget=20_000)
    assert any(f.kind == "fragmento-sin-motivo" for f in r.findings)


def test_prosa_congelada_sin_capitulo_bloquea() -> None:
    """Sin el capitulo, la procedencia no sirve para nada: no se puede volver a
    la fuente ni saber si el hecho sigue vigente."""
    p = assemble(agent="escritor", blocks=[
        Block(name="ancla", content="x", tokens=10, priority=Priority.UNTOUCHABLE,
              provenance=BlockProvenance.CANON),
        Block(name="frag", content="y", tokens=10, priority=Priority.RETRIEVED,
              provenance=BlockProvenance.FROZEN_PROSE, quota=Quota.FREE),
    ])
    r = audit(p, active_cast=[], budget=20_000)
    assert any(f.kind == "prosa-sin-capitulo" for f in r.findings)


def test_la_degradacion_se_marca_pero_no_bloquea() -> None:
    """RF-78. Recuperar peor una vez no es lo mismo que generar sobre un hecho
    falso: no aplica el fallo cerrado."""
    p = assemble(agent="escritor", blocks=_minimo(), degraded=True)
    r = audit(p, active_cast=[], budget=20_000)
    assert any(f.kind == "recuperacion-degradada" for f in r.findings)
    assert not r.blocks_generation
