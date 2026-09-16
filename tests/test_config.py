"""La configuration et son exemple ne doivent pas deriver l'un de l'autre."""

from __future__ import annotations

from pathlib import Path

from fabrique.config import Reglages

EXEMPLE = Path(__file__).resolve().parent.parent / ".env.exemple"


def _variables_documentees() -> set[str]:
    lignes = EXEMPLE.read_text().splitlines()
    return {
        ligne.split("=", 1)[0].strip()
        for ligne in lignes
        if ligne.strip() and not ligne.startswith("#")
    }


def test_env_exemple_documente_toutes_les_variables() -> None:
    attendues = {nom.upper() for nom in Reglages.model_fields}
    manquantes = attendues - _variables_documentees()
    assert not manquantes, f"absentes de .env.exemple : {sorted(manquantes)}"


def test_env_exemple_n_invente_pas_de_variable() -> None:
    connues = {nom.upper() for nom in Reglages.model_fields}
    inventees = _variables_documentees() - connues
    assert not inventees, f"inconnues de Reglages : {sorted(inventees)}"


def test_sans_host_postgres_aucun_dsn_nest_construit() -> None:
    assert Reglages(postgres_host="").dsn == ""


def test_la_chaine_de_fournisseurs_se_decoupe() -> None:
    assert Reglages(fournisseurs="ovhcloud, anthropic ,fake").chaine == [
        "ovhcloud",
        "anthropic",
        "fake",
    ]


def test_l_exemple_donne_un_mot_de_passe_postgres_utilisable() -> None:
    """`cp .env.exemple .env && docker compose up` doit marcher sans edition.

    Le compose declare POSTGRES_PASSWORD avec `:?`, donc une valeur vide le fait
    echouer aussi surement qu'une variable absente.
    """
    lignes = dict(
        ligne.split("=", 1)
        for ligne in EXEMPLE.read_text().splitlines()
        if ligne.strip() and not ligne.startswith("#") and "=" in ligne
    )
    assert lignes.get("POSTGRES_PASSWORD"), "POSTGRES_PASSWORD vide dans .env.exemple"
