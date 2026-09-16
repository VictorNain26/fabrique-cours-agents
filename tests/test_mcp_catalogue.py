"""Tests d'execution reelle du serveur MCP du catalogue, en memoire."""

from __future__ import annotations

import pytest

from fabrique.mcp_catalogue import catalogue
from fabrique.mcp_catalogue.serveur import construire


@pytest.fixture
def serveur():
    return construire()


@pytest.mark.asyncio
async def test_expose_les_trois_outils(serveur):
    outils = await serveur.list_tools()
    noms = {outil.name for outil in outils}
    assert noms == {"chercher_produit", "get_produit", "resoudre_prix"}


@pytest.mark.asyncio
async def test_descriptions_suffisamment_longues_et_negatives(serveur):
    outils = await serveur.list_tools()
    for outil in outils:
        assert outil.description is not None
        assert len(outil.description) > 60
        assert "pas" in outil.description.lower()


@pytest.mark.asyncio
async def test_noms_de_parametres_assez_longs(serveur):
    outils = await serveur.list_tools()
    for outil in outils:
        proprietes = outil.input_schema.get("properties", {})
        for nom_parametre in proprietes:
            assert len(nom_parametre) >= 4


@pytest.mark.asyncio
async def test_parametres_requis_marques(serveur):
    outils = await serveur.list_tools()
    for outil in outils:
        requis = outil.input_schema.get("required", [])
        proprietes = outil.input_schema.get("properties", {})
        assert set(requis) == set(proprietes)
        assert len(requis) >= 1


@pytest.mark.asyncio
async def test_resoudre_prix_renvoie_le_bon_prix(serveur):
    reference = "vps-comfort"
    produit_attendu = catalogue.get(reference)

    resultat = await serveur.call_tool("resoudre_prix", {"reference": reference})

    assert resultat.is_error is False
    assert resultat.structured_content["reference"] == reference
    assert resultat.structured_content["prix_mensuel_eur"] == produit_attendu.prix_mensuel_eur


@pytest.mark.asyncio
async def test_chercher_produit_trouve_par_gamme(serveur):
    resultat = await serveur.call_tool("chercher_produit", {"requete_en_langage_naturel": "entree"})

    references = {produit["reference"] for produit in resultat.structured_content["result"]}
    assert "vps-starter" in references


@pytest.mark.asyncio
async def test_get_produit_reference_inconnue_renvoie_none(serveur):
    resultat = await serveur.call_tool("get_produit", {"reference": "inexistant"})

    assert resultat.structured_content["result"] is None


def test_le_client_resout_le_prix_par_le_protocole() -> None:
    from fabrique.mcp_catalogue.client import resoudre_prix

    prix = resoudre_prix("vps-comfort")

    assert prix is not None
    assert prix.prix_mensuel_eur == catalogue.get("vps-comfort").prix_mensuel_eur


def test_le_client_rend_none_pour_une_reference_inconnue() -> None:
    from fabrique.mcp_catalogue.client import resoudre_prix

    assert resoudre_prix("inexistant") is None


@pytest.mark.asyncio
async def test_une_reference_inconnue_est_une_erreur_d_outil_nommee(serveur):
    from mcp import Client

    async with Client(serveur) as client:
        resultat = await client.call_tool("resoudre_prix", {"reference": "inexistant"})

    assert resultat.is_error is True
    assert "inexistant" in resultat.content[0].text
