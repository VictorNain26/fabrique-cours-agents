"""Tests du validateur deterministe de garde-fous."""

from __future__ import annotations

import pytest

from fabrique.garde_fous.validateur import bloquantes, valider
from fabrique.modeles import BlocPage, Page

META_VALIDE = "M" * 130


def page_propre() -> Page:
    return Page(
        titre_h1="Un titre correct",
        meta_description=META_VALIDE,
        blocs=[
            BlocPage(type="titre", contenu="Un titre correct"),
            BlocPage(type="paragraphe", contenu="Un paragraphe sans prix ni montant."),
            BlocPage(type="tableau_prix", contenu="Voir nos offres", product_ref="ref-42"),
        ],
        liens=["/accueil"],
    )


def test_page_propre_ne_leve_rien():
    violations = valider(page_propre(), pages_existantes={"/accueil"})

    assert violations == []


def test_h1_multiple_sans_titre():
    page = page_propre()
    page.blocs = [bloc for bloc in page.blocs if bloc.type != "titre"]

    violations = valider(page, pages_existantes={"/accueil"})

    codes = [v.code for v in violations]
    assert "H1_MULTIPLE" in codes
    violation = next(v for v in violations if v.code == "H1_MULTIPLE")
    assert violation.gravite == "bloquant"
    assert violation.indice


def test_h1_multiple_avec_deux_titres():
    page = page_propre()
    page.blocs.append(BlocPage(type="titre", contenu="Un second titre"))

    violations = valider(page, pages_existantes={"/accueil"})

    codes = [v.code for v in violations]
    assert codes.count("H1_MULTIPLE") == 1


@pytest.mark.parametrize(
    "contenu",
    [
        "Cet abonnement coute 4,99 €",
        "Facture de 12 EUR par mois",
        "Prix : 3.50€",
        "Disponible a partir de 9 euros",
    ],
)
def test_prix_en_dur_detecte(contenu: str):
    page = page_propre()
    page.blocs[1] = BlocPage(type="paragraphe", contenu=contenu)

    violations = valider(page, pages_existantes={"/accueil"})

    codes = [v.code for v in violations]
    assert "PRIX_EN_DUR" in codes
    violation = next(v for v in violations if v.code == "PRIX_EN_DUR")
    assert violation.gravite == "bloquant"
    assert violation.indice


@pytest.mark.parametrize("contenu", ["Serveur avec 4 vCores", "Sorti en 2024"])
def test_prix_en_dur_pas_de_faux_positif(contenu: str):
    page = page_propre()
    page.blocs[1] = BlocPage(type="paragraphe", contenu=contenu)

    violations = valider(page, pages_existantes={"/accueil"})

    codes = [v.code for v in violations]
    assert "PRIX_EN_DUR" not in codes


def test_ref_produit_manquante():
    page = page_propre()
    page.blocs[2] = BlocPage(type="tableau_prix", contenu="Voir nos offres", product_ref=None)

    violations = valider(page, pages_existantes={"/accueil"})

    codes = [v.code for v in violations]
    assert "REF_PRODUIT_MANQUANTE" in codes
    violation = next(v for v in violations if v.code == "REF_PRODUIT_MANQUANTE")
    assert violation.gravite == "bloquant"
    assert violation.indice


def test_lien_mort():
    page = page_propre()
    page.liens = ["/accueil", "/page-inexistante"]

    violations = valider(page, pages_existantes={"/accueil"})

    codes = [v.code for v in violations]
    assert "LIEN_MORT" in codes
    violation = next(v for v in violations if v.code == "LIEN_MORT")
    assert violation.gravite == "avertissement"
    assert violation.indice


def test_bloquantes_filtre_les_avertissements():
    page = page_propre()
    page.liens = ["/page-inexistante"]

    violations = valider(page, pages_existantes=set())

    assert bloquantes(violations) == []
    assert len(violations) == 1
    assert violations[0].gravite == "avertissement"
