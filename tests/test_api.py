"""Tests de l'API HTTP : fournisseur fake, checkpointer en memoire, sans reseau."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fabrique.config import reglages


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FOURNISSEURS", "fake")
    monkeypatch.setenv("POSTGRES_HOST", "")
    reglages.cache_clear()

    from fabrique.api import app

    with TestClient(app) as client:
        yield client

    reglages.cache_clear()


def test_sante(client: TestClient) -> None:
    reponse = client.get("/sante")

    assert reponse.status_code == 200
    assert reponse.json() == {"statut": "ok", "fournisseurs": ["fake"]}


def test_creer_page_renvoie_un_thread_id_et_un_statut_coherent(client: TestClient) -> None:
    reponse = client.post("/pages", json={"brief": "brief", "pages_existantes": []})

    assert reponse.status_code == 202
    corps = reponse.json()
    assert corps["thread_id"]
    assert corps["statut"] == "en_attente_validation"
    assert corps["page"] is not None


def test_lire_un_thread_inconnu_renvoie_404(client: TestClient) -> None:
    reponse = client.get("/pages/inconnu")

    assert reponse.status_code == 404


def test_validation_approuvee_publie_la_page(client: TestClient) -> None:
    creation = client.post("/pages", json={"brief": "brief", "pages_existantes": []})
    thread_id = creation.json()["thread_id"]

    reponse = client.post(
        f"/pages/{thread_id}/validation", json={"approuve": True, "commentaire": "ok"}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "publiee"
    assert corps["identifiant_publication"]


def test_validation_refusee_ne_publie_pas(client: TestClient) -> None:
    creation = client.post("/pages", json={"brief": "brief", "pages_existantes": []})
    thread_id = creation.json()["thread_id"]

    reponse = client.post(
        f"/pages/{thread_id}/validation", json={"approuve": False, "commentaire": "non"}
    )

    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["statut"] == "refusee"
    assert corps["identifiant_publication"] is None


def test_validation_sur_un_thread_inconnu_renvoie_404(client: TestClient) -> None:
    reponse = client.post("/pages/inconnu/validation", json={"approuve": True})

    assert reponse.status_code == 404


def test_validation_deja_traitee_renvoie_409(client: TestClient) -> None:
    creation = client.post("/pages", json={"brief": "brief", "pages_existantes": []})
    thread_id = creation.json()["thread_id"]
    client.post(f"/pages/{thread_id}/validation", json={"approuve": True})

    reponse = client.post(f"/pages/{thread_id}/validation", json={"approuve": True})

    assert reponse.status_code == 409


def test_la_reponse_expose_qui_a_repondu_et_le_cout(client: TestClient) -> None:
    """Un repli invisible cote HTTP fausse toute analyse a posteriori."""
    reponse = client.post("/pages", json={"brief": "brief", "pages_existantes": []})
    corps = reponse.json()

    assert corps["fournisseur"] == "fake"
    assert corps["cout"] is not None

    relu = client.get(f"/pages/{corps['thread_id']}").json()
    assert relu["fournisseur"] == "fake"


def test_une_page_avec_tableau_de_prix_passe_par_mcp_via_l_api(client, monkeypatch) -> None:
    import json

    from fabrique.providers.fake import FournisseurFake

    page = json.dumps(
        {
            "titre_h1": "VPS",
            "meta_description": "d" * 130,
            "blocs": [
                {"type": "titre", "contenu": "VPS"},
                {"type": "tableau_prix", "contenu": "Offres", "product_ref": "vps-pro"},
            ],
            "liens": [],
        }
    )
    client.app.state.fournisseurs = [FournisseurFake(reponses=[page])]

    corps = client.post("/pages", json={"brief": "b"}).json()

    assert corps["page"]["blocs"][1]["prix_affiche"] == "31.99 EUR / mois"


def test_les_routes_ne_bloquent_pas_la_boucle() -> None:
    import inspect

    from fabrique import api

    for route in (api.sante, api.creer_page, api.lire_page, api.valider_page):
        assert not inspect.iscoroutinefunction(route), route.__name__


def test_le_budget_de_tokens_invite_atteint_le_graphe(client: TestClient, monkeypatch) -> None:
    from fabrique import api
    from fabrique.generation.graphe import construire as construire_reel

    monkeypatch.setenv("BUDGET_TOKENS_INVITE", "777")
    reglages.cache_clear()

    captures: dict = {}

    def espion(*args, **kwargs):
        captures.update(kwargs)
        return construire_reel(*args, **kwargs)

    monkeypatch.setattr(api, "construire", espion)

    client.post("/pages", json={"brief": "b", "pages_existantes": []})

    assert captures["budget_tokens_invite"] == 777


def test_un_budget_epuise_sur_plusieurs_tours_renvoie_402(client: TestClient) -> None:
    import json

    from fabrique.providers.fake import FournisseurFake

    def page(titres: int) -> str:
        return json.dumps(
            {
                "titre_h1": "VPS",
                "meta_description": "d" * 130,
                "blocs": [{"type": "titre", "contenu": f"Titre {i}"} for i in range(titres)],
                "liens": [],
            }
        )

    fournisseur = FournisseurFake(reponses=[page(2), page(1)])
    fournisseur.cout_par_appel = reglages().budget_par_page * 0.6
    client.app.state.fournisseurs = [fournisseur]

    reponse = client.post("/pages", json={"brief": "b"})

    assert reponse.status_code == 402
    assert "budget" in reponse.json()["detail"]


def test_un_catalogue_en_panne_renvoie_un_503_json(client: TestClient, monkeypatch) -> None:
    import json

    from fabrique.providers.fake import FournisseurFake

    def en_panne(_reference):
        raise ValueError("catalogue en panne")

    monkeypatch.setattr("fabrique.mcp_catalogue.catalogue.get", en_panne)
    page = json.dumps(
        {
            "titre_h1": "VPS",
            "meta_description": "d" * 130,
            "blocs": [
                {"type": "titre", "contenu": "VPS"},
                {"type": "tableau_prix", "contenu": "Offres", "product_ref": "vps-pro"},
            ],
            "liens": [],
        }
    )
    client.app.state.fournisseurs = [FournisseurFake(reponses=[page])]
    sans_relance = TestClient(client.app, raise_server_exceptions=False)

    reponse = sans_relance.post("/pages", json={"brief": "b"})

    assert reponse.status_code == 503
    assert reponse.headers["content-type"] == "application/json"
    assert reponse.json()["detail"]
