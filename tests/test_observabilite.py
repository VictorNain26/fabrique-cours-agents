"""L'instrumentation doit etre cablee dans le pipeline, et inoffensive sans cles."""

from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver

from fabrique import observabilite
from fabrique.generation.graphe import construire
from fabrique.modeles import Violation
from fabrique.providers.fake import FournisseurFake


def test_sans_cles_l_instrumentation_est_inoffensive() -> None:
    assert observabilite.actif() is False
    observabilite.tracer_violation(Violation(code="X", gravite="bloquant", message="m", indice="i"))
    observabilite.vider()


def test_observe_laisse_la_fonction_fonctionner() -> None:
    @observabilite.observe()
    def double(n: int) -> int:
        return n * 2

    assert double(21) == 42


def test_le_noeud_de_controle_trace_les_violations(monkeypatch) -> None:
    """Le cablage reel : sans ce test, observabilite.py serait du code mort."""
    vues: list[str] = []
    monkeypatch.setattr(
        "fabrique.generation.graphe.tracer_violation",
        lambda v: vues.append(v.code),
    )

    graphe = construire([FournisseurFake()], set(), checkpointer=InMemorySaver())
    graphe.invoke({"brief": "page"}, config={"configurable": {"thread_id": "obs-1"}})

    assert vues, "aucune violation tracee alors que le fake produit des liens morts"
    assert all(isinstance(code, str) for code in vues)


def test_observation_accepte_un_nom_de_trace_explicite(spans) -> None:
    from langfuse._client.attributes import LangfuseOtelSpanAttributes

    with observabilite.observation("x", fil="f", trace="tuteur"):
        pass

    (trace,) = [
        s for s in spans() if s.attributes.get(LangfuseOtelSpanAttributes.TRACE_NAME) == "tuteur"
    ]
    assert trace.attributes[LangfuseOtelSpanAttributes.TRACE_NAME] == "tuteur"
