"""Tests d'integration contre les vraies API. Ignores par defaut.

Ils coutent de l'argent, donc ils ne tournent ni en CI ni par accident :
il faut poser FABRIQUE_TESTS_REELS=1 ET la cle du fournisseur vise.

    FABRIQUE_TESTS_REELS=1 .venv/bin/python -m pytest tests/test_providers_reels.py -v
"""

from __future__ import annotations

import os

import pytest

from fabrique.config import reglages
from fabrique.garde_fous import bloquantes
from fabrique.garde_fous.validateur import valider
from fabrique.generation.reparation import generer_valide
from fabrique.modeles import Page

INVITE = (
    "Redige une page de vente courte pour une offre de VPS destinee aux developpeurs. "
    "Un seul bloc de type titre. Chaque bloc fait moins de 200 caracteres. "
    "Pas de prix en dur : un bloc tableau_prix avec product_ref='vps-comfort'."
)
SYSTEME = "Tu generes une page web au format JSON strict conforme au schema fourni."

actif = pytest.mark.skipif(
    os.environ.get("FABRIQUE_TESTS_REELS") != "1",
    reason="pose FABRIQUE_TESTS_REELS=1 pour lancer les appels payants",
)


def _controle_commun(page: Page) -> None:
    assert isinstance(page, Page)
    assert 120 <= len(page.meta_description) <= 158
    assert sum(1 for b in page.blocs if b.type == "titre") == 1
    assert not bloquantes(valider(page, {"/vps", "/stockage"}))


@actif
def test_ovhcloud_produit_une_page_conforme() -> None:
    if not reglages().ovh_api_key:
        pytest.skip("OVH_API_KEY absente")
    from fabrique.providers.ovhcloud import FournisseurOVHcloud

    fournisseur = FournisseurOVHcloud(
        api_key=reglages().ovh_api_key,
        base_url=reglages().ovh_base_url,
        modele=reglages().ovh_modele,
    )
    _controle_commun(
        generer_valide(fournisseur, invite=INVITE, schema=Page, systeme=SYSTEME, max_essais=3)
    )


@actif
def test_anthropic_produit_une_page_conforme() -> None:
    if not reglages().anthropic_api_key:
        pytest.skip("ANTHROPIC_API_KEY absente")
    from fabrique.providers.anthropic import FournisseurAnthropic

    fournisseur = FournisseurAnthropic(
        api_key=reglages().anthropic_api_key,
        modele=reglages().anthropic_modele,
    )
    _controle_commun(
        generer_valide(fournisseur, invite=INVITE, schema=Page, systeme=SYSTEME, max_essais=3)
    )


@actif
def test_une_cle_invalide_donne_une_fatale_pas_une_surcharge() -> None:
    """La frontiere doit classer correctement, sinon le repli boucle pour rien."""
    from fabrique.providers.base import Fatale
    from fabrique.providers.ovhcloud import FournisseurOVHcloud

    fournisseur = FournisseurOVHcloud(api_key="cle-invalide", base_url=reglages().ovh_base_url)
    with pytest.raises(Fatale):
        fournisseur.generer(invite="test", schema=Page)
