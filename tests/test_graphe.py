from __future__ import annotations

import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from fabrique.generation.graphe import construire
from fabrique.providers.fake import FournisseurFake

META = "A" * 130


def _page_json(titre_unique: bool) -> str:
    blocs = [{"type": "titre", "contenu": "Titre unique"}]
    if not titre_unique:
        blocs.append({"type": "titre", "contenu": "Second titre"})
    else:
        blocs.append({"type": "paragraphe", "contenu": "Un paragraphe sans prix."})
    return json.dumps(
        {
            "titre_h1": "Titre",
            "meta_description": META,
            "blocs": blocs,
            "liens": [],
        }
    )


PAGE_INVALIDE = _page_json(titre_unique=False)
PAGE_VALIDE = _page_json(titre_unique=True)


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def test_correction_tourne_puis_sarrete_sans_violation_bloquante():
    fournisseur = FournisseurFake(reponses=[PAGE_INVALIDE, PAGE_VALIDE])
    graphe = construire([fournisseur], set(), checkpointer=InMemorySaver(), max_tours=3)

    resultat = graphe.invoke({"brief": "brief"}, config=_config("t1"))

    assert resultat["essais"] == 2
    assert resultat["violations"] == []
    assert "__interrupt__" in resultat


def test_max_tours_borne_le_nombre_dessais():
    fournisseur = FournisseurFake(reponses=[PAGE_INVALIDE])
    graphe = construire([fournisseur], set(), checkpointer=InMemorySaver(), max_tours=2)

    resultat = graphe.invoke({"brief": "brief"}, config=_config("t2"))

    assert resultat["essais"] == 2
    assert any(v["code"] == "H1_MULTIPLE" for v in resultat["violations"])


def test_le_graphe_sinterrompt_a_la_validation_humaine():
    fournisseur = FournisseurFake(reponses=[PAGE_VALIDE])
    graphe = construire([fournisseur], set(), checkpointer=InMemorySaver(), max_tours=3)
    config = _config("t3")

    resultat = graphe.invoke({"brief": "brief"}, config=config)

    interruptions = resultat["__interrupt__"]
    assert len(interruptions) == 1
    assert set(interruptions[0].value.keys()) == {"page", "violations"}

    etat = graphe.get_state(config)
    assert etat.next == ("validation_humaine",)


def test_reprise_approuvee_publie_une_seule_fois():
    appels: list[str] = []

    def publier(page):
        appels.append(page.titre_h1)
        return "id-1"

    fournisseur = FournisseurFake(reponses=[PAGE_VALIDE])
    graphe = construire(
        [fournisseur], set(), checkpointer=InMemorySaver(), max_tours=3, publier=publier
    )
    config = _config("t4")

    graphe.invoke({"brief": "brief"}, config=config)
    resultat = graphe.invoke(Command(resume={"approuve": True, "commentaire": "ok"}), config=config)

    assert resultat["publiee"] is True
    assert len(appels) == 1


def test_reprise_refusee_ne_publie_pas():
    appels: list[str] = []

    def publier(page):
        appels.append(page.titre_h1)
        return "id-1"

    fournisseur = FournisseurFake(reponses=[PAGE_VALIDE])
    graphe = construire(
        [fournisseur], set(), checkpointer=InMemorySaver(), max_tours=3, publier=publier
    )
    config = _config("t5")

    graphe.invoke({"brief": "brief"}, config=config)
    resultat = graphe.invoke(
        Command(resume={"approuve": False, "commentaire": "non"}), config=config
    )

    assert resultat.get("publiee") is not True
    assert appels == []


def test_tous_les_noeuds_sont_declares():
    fournisseur = FournisseurFake(reponses=[PAGE_VALIDE])
    graphe = construire([fournisseur], set(), checkpointer=InMemorySaver())

    noms = set(graphe.get_graph().nodes)

    assert {
        "redaction",
        "controle",
        "correction",
        "validation_humaine",
        "publication",
    } <= noms


def test_le_graphe_bascule_sur_le_fournisseur_suivant_et_trace_lequel() -> None:
    from fabrique.providers.base import Surcharge

    sature = FournisseurFake(reponses=[PAGE_VALIDE], erreurs=[Surcharge()])
    sature.nom = "sature"
    secours = FournisseurFake(reponses=[PAGE_VALIDE])
    secours.nom = "secours"

    graphe = construire([sature, secours], set(), checkpointer=InMemorySaver())
    etat = graphe.invoke({"brief": "brief"}, config=_config("repli-1"))

    assert etat["fournisseur"] == "secours"
    assert etat["page"] is not None


def test_le_budget_arrete_la_chaine_avant_l_appel() -> None:
    from fabrique.providers.base import BudgetDepasse

    cher = FournisseurFake(reponses=[PAGE_VALIDE])
    cher.cout_par_appel = 10.0

    graphe = construire([cher], set(), checkpointer=InMemorySaver(), budget_par_page=0.5)
    with pytest.raises(BudgetDepasse):
        graphe.invoke({"brief": "brief"}, config=_config("budget-1"))
