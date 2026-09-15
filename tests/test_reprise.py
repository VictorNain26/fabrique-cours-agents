from langgraph.checkpoint.memory import InMemorySaver

from fabrique.generation.graphe import construire
from fabrique.generation.reprise import en_attente, interruption, reprendre
from fabrique.providers.fake import FournisseurFake

PAGES = {"/vps"}


def monter():
    publiees = []
    graphe = construire(
        FournisseurFake(),
        PAGES,
        checkpointer=InMemorySaver(),
        publier=lambda page: publiees.append(page) or "pub-1",
    )
    return graphe, publiees


def test_interruption_detectee():
    graphe, _ = monter()
    config = {"configurable": {"thread_id": "t1"}}
    etat = graphe.invoke({"brief": "page vps", "essais": 0}, config=config)

    inter = interruption(etat, graphe, config)
    assert inter is not None
    assert inter.noeud == "validation_humaine"
    assert en_attente(graphe, config)


def test_reprise_approuvee_publie_une_fois():
    graphe, publiees = monter()
    config = {"configurable": {"thread_id": "t2"}}
    graphe.invoke({"brief": "page vps", "essais": 0}, config=config)

    final = reprendre(graphe, config, approuve=True, commentaire="ok")
    assert final.get("publiee") is True
    assert len(publiees) == 1
    assert not en_attente(graphe, config)


def test_reprise_refusee_ne_publie_pas():
    graphe, publiees = monter()
    config = {"configurable": {"thread_id": "t3"}}
    graphe.invoke({"brief": "page vps", "essais": 0}, config=config)

    final = reprendre(graphe, config, approuve=False, commentaire="a revoir")
    assert not final.get("publiee")
    assert publiees == []


def test_pas_d_interruption_quand_termine():
    graphe, _ = monter()
    config = {"configurable": {"thread_id": "t4"}}
    graphe.invoke({"brief": "page vps", "essais": 0}, config=config)
    final = reprendre(graphe, config, approuve=True)
    assert interruption(final, graphe, config) is None
