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
