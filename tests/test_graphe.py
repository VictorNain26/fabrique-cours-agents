from __future__ import annotations

import json

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from fabrique.generation.graphe import construire
from fabrique.mcp_catalogue.serveur import PrixResolu
from fabrique.modeles import Violation
from fabrique.providers.fake import FournisseurFake
from fabrique.providers.repli import executer

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


def _page_avec_tableau(reference, prix_affiche=None):
    return json.dumps(
        {
            "titre_h1": "Titre",
            "meta_description": META,
            "blocs": [
                {"type": "titre", "contenu": "Titre unique"},
                {
                    "type": "tableau_prix",
                    "contenu": "Nos offres",
                    "product_ref": reference,
                    "prix_affiche": prix_affiche,
                },
            ],
            "liens": [],
        }
    )


PAGE_INVALIDE = _page_json(titre_unique=False)
PAGE_VALIDE = _page_json(titre_unique=True)


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _valider_titre_unique(page, pages_existantes):
    titres = sum(1 for b in page.blocs if b.type == "titre")
    if titres == 1:
        return []
    return [Violation(code="H1_MULTIPLE", gravite="bloquant", message="titres", indice="un seul")]


def _prix_connus(reference):
    if reference != "vps-comfort":
        return None
    return PrixResolu(
        reference=reference, prix_mensuel_eur=7.99, libelle_affichable="7.99 EUR / mois"
    )


def _graphe(fournisseurs, **options):
    options.setdefault("checkpointer", InMemorySaver())
    options.setdefault("valider", _valider_titre_unique)
    options.setdefault("resoudre_prix", _prix_connus)
    return construire(fournisseurs, set(), **options)


def test_correction_tourne_puis_sarrete_sans_violation_bloquante():
    fournisseur = FournisseurFake(reponses=[PAGE_INVALIDE, PAGE_VALIDE])
    graphe = _graphe([fournisseur], max_tours=3)

    resultat = graphe.invoke({"brief": "brief"}, config=_config("t1"))

    assert resultat["essais"] == 2
    assert resultat["violations"] == []
    assert "__interrupt__" in resultat


def test_max_tours_borne_le_nombre_dessais():
    fournisseur = FournisseurFake(reponses=[PAGE_INVALIDE])
    graphe = _graphe([fournisseur], max_tours=2)

    resultat = graphe.invoke({"brief": "brief"}, config=_config("t2"))

    assert resultat["essais"] == 2
    assert any(v["code"] == "H1_MULTIPLE" for v in resultat["violations"])


def test_le_graphe_sinterrompt_a_la_validation_humaine():
    fournisseur = FournisseurFake(reponses=[PAGE_VALIDE])
    graphe = _graphe([fournisseur], max_tours=3)
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
    graphe = _graphe([fournisseur], max_tours=3, publier=publier)
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
    graphe = _graphe([fournisseur], max_tours=3, publier=publier)
    config = _config("t5")

    graphe.invoke({"brief": "brief"}, config=config)
    resultat = graphe.invoke(
        Command(resume={"approuve": False, "commentaire": "non"}), config=config
    )

    assert resultat.get("publiee") is not True
    assert appels == []


def test_tous_les_noeuds_sont_declares():
    graphe = _graphe([FournisseurFake(reponses=[PAGE_VALIDE])])

    noms = set(graphe.get_graph().nodes)

    assert {
        "redaction",
        "controle",
        "correction",
        "tarification",
        "validation_humaine",
        "publication",
    } <= noms


def test_la_tarification_renseigne_le_prix_depuis_le_resolveur():
    page = _page_avec_tableau("vps-comfort")
    graphe = _graphe([FournisseurFake(reponses=[page])])

    etat = graphe.invoke({"brief": "b"}, config=_config("prix-1"))

    blocs = etat["page"]["blocs"]
    assert [b["prix_affiche"] for b in blocs] == [None, "7.99 EUR / mois"]


def test_le_modele_ne_peut_pas_imposer_son_propre_prix():
    page = _page_avec_tableau("vps-comfort", prix_affiche="0.01 EUR")
    graphe = _graphe([FournisseurFake(reponses=[page])])

    etat = graphe.invoke({"brief": "b"}, config=_config("prix-2"))

    assert etat["page"]["blocs"][1]["prix_affiche"] == "7.99 EUR / mois"


def test_une_reference_inconnue_repart_en_correction():
    fournisseur = FournisseurFake(
        reponses=[_page_avec_tableau("inventee"), _page_avec_tableau("vps-comfort")]
    )
    graphe = _graphe([fournisseur])

    etat = graphe.invoke({"brief": "b"}, config=_config("prix-3"))

    assert etat["essais"] == 2
    assert "REF_PRODUIT_INCONNUE" in fournisseur.appels[1]["invite"]
    assert "__interrupt__" in etat


def test_les_retours_sont_compactes_sous_le_budget():
    vus = []

    def compacter_espion(messages, budget, resumer):
        vus.append((len(messages), budget))
        return messages

    fournisseur = FournisseurFake(reponses=[PAGE_INVALIDE, PAGE_INVALIDE, PAGE_VALIDE])
    graphe = _graphe(
        [fournisseur], compacter=compacter_espion, budget_tokens_invite=321, max_tours=3
    )

    graphe.invoke({"brief": "b"}, config=_config("ctx-1"))

    assert vus == [(1, 321), (2, 321), (3, 321)]


def test_un_retour_ecarte_est_resume_par_ses_codes():
    fournisseur = FournisseurFake(reponses=[PAGE_INVALIDE, PAGE_INVALIDE, PAGE_VALIDE])
    graphe = _graphe([fournisseur], budget_tokens_invite=20, max_tours=3)

    graphe.invoke({"brief": "b" * 40}, config=_config("ctx-2"))

    derniere_invite = fournisseur.appels[2]["invite"]
    assert "retours precedents resumes : H1_MULTIPLE" in derniere_invite
    assert "retour_correction" not in derniere_invite


def test_les_dependances_injectees_sont_utilisees():
    appels = []

    def repli_espion(fournisseurs, budget, appel):
        appels.append(budget)
        return executer(fournisseurs, budget, appel)

    graphe = _graphe(
        [FournisseurFake(reponses=[PAGE_VALIDE])], repli=repli_espion, budget_par_page=0.3
    )
    graphe.invoke({"brief": "b"}, config=_config("di-1"))

    assert appels == [0.3]


def test_le_graphe_bascule_sur_le_fournisseur_suivant_et_trace_lequel() -> None:
    from fabrique.providers.base import Surcharge

    sature = FournisseurFake(reponses=[PAGE_VALIDE], erreurs=[Surcharge()])
    sature.nom = "sature"
    secours = FournisseurFake(reponses=[PAGE_VALIDE])
    secours.nom = "secours"

    graphe = _graphe([sature, secours])
    etat = graphe.invoke({"brief": "brief"}, config=_config("repli-1"))

    assert etat["fournisseur"] == "secours"
    assert etat["page"] is not None


def test_a_la_limite_des_tours_les_violations_de_controle_et_de_tarification_remontent() -> None:
    page = json.dumps(
        {
            "titre_h1": "Titre",
            "meta_description": META,
            "blocs": [
                {"type": "titre", "contenu": "Titre un"},
                {"type": "titre", "contenu": "Titre deux"},
                {
                    "type": "tableau_prix",
                    "contenu": "Nos offres",
                    "product_ref": "inventee",
                },
            ],
            "liens": [],
        }
    )
    fournisseur = FournisseurFake(reponses=[page])
    graphe = _graphe([fournisseur], max_tours=1)

    resultat = graphe.invoke({"brief": "b"}, config=_config("limite-1"))

    interruption = resultat["__interrupt__"][0]
    codes = {v["code"] for v in interruption.value["violations"]}
    assert codes == {"H1_MULTIPLE", "REF_PRODUIT_INCONNUE"}


def test_le_budget_arrete_la_chaine_avant_l_appel() -> None:
    from fabrique.providers.base import BudgetDepasse

    cher = FournisseurFake(reponses=[PAGE_VALIDE])
    cher.cout_par_appel = 10.0

    graphe = _graphe([cher], budget_par_page=0.5)
    with pytest.raises(BudgetDepasse):
        graphe.invoke({"brief": "brief"}, config=_config("budget-1"))


def test_le_budget_couvre_la_page_entiere_pas_chaque_tour() -> None:
    from fabrique.providers.base import BudgetDepasse

    fournisseur = FournisseurFake(reponses=[PAGE_INVALIDE, PAGE_VALIDE])
    fournisseur.cout_par_appel = 0.3

    graphe = _graphe([fournisseur], budget_par_page=0.5, max_tours=3)
    with pytest.raises(BudgetDepasse):
        graphe.invoke({"brief": "brief"}, config=_config("budget-2"))

    assert len(fournisseur.appels) == 1


def test_le_cout_de_la_page_cumule_tous_les_tours() -> None:
    fournisseur = FournisseurFake(reponses=[PAGE_INVALIDE, PAGE_VALIDE])
    fournisseur.cout_par_appel = 0.1

    graphe = _graphe([fournisseur], budget_par_page=0.5, max_tours=3)
    etat = graphe.invoke({"brief": "brief"}, config=_config("budget-3"))

    assert etat["cout"] == pytest.approx(0.2)
    assert "redaction: essai 2, fake, 0.2000 EUR" in etat["journal"]
