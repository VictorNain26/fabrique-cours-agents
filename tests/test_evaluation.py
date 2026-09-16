"""Tests du dataset golden et du harnais d'evaluation. Aucun reseau, aucune cle."""

from __future__ import annotations

import pytest
from langfuse import RegressionError

from fabrique.evaluation.dataset import CAS
from fabrique.evaluation.evaluateurs import (
    refs_produit_resolues,
    respecte_longueurs,
    sans_violation_bloquante,
)
from fabrique.evaluation.experience import exiger_non_regression, lancer_local, verdict

META_VALIDE = "M" * 130

PAGE_BONNE = {
    "titre_h1": "Un titre correct",
    "meta_description": META_VALIDE,
    "blocs": [
        {"type": "titre", "contenu": "Un titre correct"},
        {"type": "paragraphe", "contenu": "Un paragraphe sans prix ni montant."},
        {
            "type": "tableau_prix",
            "contenu": "Voir nos offres",
            "product_ref": "vps-comfort",
            "prix_affiche": "7.99 EUR / mois",
        },
    ],
    "liens": ["/accueil"],
}


def _page_avec(**remplacements):
    page = {**PAGE_BONNE, **remplacements}
    return page


class TestSansViolationBloquante:
    def test_page_propre_est_notee_un(self):
        evaluation = sans_violation_bloquante(
            input="brief",
            output=PAGE_BONNE,
            expected_output={},
            metadata={"pages_existantes": ["/accueil"]},
        )

        assert evaluation.name == "sans_violation_bloquante"
        assert evaluation.value == 1.0

    def test_deux_h1_est_notee_zero(self):
        page = _page_avec(
            blocs=[
                *PAGE_BONNE["blocs"],
                {"type": "titre", "contenu": "Un second titre"},
            ]
        )

        evaluation = sans_violation_bloquante(
            input="brief",
            output=page,
            expected_output={},
            metadata={"pages_existantes": ["/accueil"]},
        )

        assert evaluation.value == 0.0
        assert "H1_MULTIPLE" in evaluation.comment

    def test_codes_interdits_font_echouer_meme_en_avertissement(self):
        page = _page_avec(liens=["/page-inexistante"])

        evaluation = sans_violation_bloquante(
            input="brief",
            output=page,
            expected_output={"codes_interdits": ["LIEN_MORT"]},
            metadata={"pages_existantes": []},
        )

        assert evaluation.value == 0.0


class TestRespecteLongueurs:
    def test_page_bonne_est_notee_un(self):
        evaluation = respecte_longueurs(input="brief", output=PAGE_BONNE)

        assert evaluation.value == 1.0

    @pytest.mark.parametrize("longueur", [119, 159])
    def test_meta_description_hors_bornes_est_notee_zero(self, longueur: int):
        page = _page_avec(meta_description="M" * longueur)

        evaluation = respecte_longueurs(input="brief", output=page)

        assert evaluation.value == 0.0

    @pytest.mark.parametrize("longueur", [120, 158])
    def test_meta_description_aux_bornes_est_notee_un(self, longueur: int):
        page = _page_avec(meta_description="M" * longueur)

        evaluation = respecte_longueurs(input="brief", output=page)

        assert evaluation.value == 1.0

    def test_titre_trop_long_est_notee_zero(self):
        page = _page_avec(titre_h1="T" * 71)

        evaluation = respecte_longueurs(input="brief", output=page)

        assert evaluation.value == 0.0


class TestRefsProduitResolues:
    def test_toutes_les_refs_presentes_est_notee_un(self):
        evaluation = refs_produit_resolues(input="brief", output=PAGE_BONNE)

        assert evaluation.value == 1.0

    def test_tableau_prix_sans_ref_est_notee_zero(self):
        page = _page_avec(
            blocs=[
                {"type": "titre", "contenu": "Un titre correct"},
                {"type": "tableau_prix", "contenu": "Voir nos offres", "product_ref": None},
            ]
        )

        evaluation = refs_produit_resolues(input="brief", output=page)

        assert evaluation.value == 0.0

    def test_tableau_prix_sans_prix_affiche_est_notee_zero(self):
        page = _page_avec(
            blocs=[
                {"type": "titre", "contenu": "Un titre correct"},
                {
                    "type": "tableau_prix",
                    "contenu": "Voir nos offres",
                    "product_ref": "vps-comfort",
                },
            ]
        )

        evaluation = refs_produit_resolues(input="brief", output=page)

        assert evaluation.value == 0.0

    def test_reference_hors_catalogue_est_notee_zero(self):
        page = _page_avec(
            blocs=[
                {"type": "titre", "contenu": "Un titre correct"},
                {
                    "type": "tableau_prix",
                    "contenu": "Voir nos offres",
                    "product_ref": "ref-42",
                    "prix_affiche": "7.99 EUR / mois",
                },
            ]
        )

        evaluation = refs_produit_resolues(input="brief", output=page)

        assert evaluation.value == 0.0

    def test_prix_affiche_different_du_catalogue_est_note_zero(self):
        page = {
            **PAGE_BONNE,
            "blocs": [
                {"type": "titre", "contenu": "Titre"},
                {
                    "type": "tableau_prix",
                    "contenu": "Offres",
                    "product_ref": "vps-comfort",
                    "prix_affiche": "1.00 EUR / mois",
                },
            ],
        }
        assert refs_produit_resolues(input="brief", output=page).value == 0.0


def _task_constante(*, item, **kwargs):
    return PAGE_BONNE


def _task_mauvaise(*, item, **kwargs):
    return _page_avec(
        blocs=[
            {"type": "titre", "contenu": "Un titre correct"},
            {"type": "titre", "contenu": "Un second titre"},
            {"type": "tableau_prix", "contenu": "Voir nos offres", "product_ref": None},
        ]
    )


def test_lancer_local_sur_task_deterministe_bonne():
    resultat = lancer_local(_task_constante)

    assert resultat["moyennes"]["sans_violation_bloquante"] == 1.0
    assert resultat["moyennes"]["respecte_longueurs"] == 1.0
    assert resultat["moyennes"]["refs_produit_resolues"] == 1.0
    assert len(resultat["detail"]) == len(CAS)


def test_lancer_local_sur_task_deterministe_mauvaise():
    resultat = lancer_local(_task_mauvaise)

    assert resultat["moyennes"]["sans_violation_bloquante"] == 0.0
    assert resultat["moyennes"]["refs_produit_resolues"] == 0.0


class TestVerdict:
    def test_amelioration(self):
        baseline = {"moyennes": {"score": 0.5}}
        candidat = {"moyennes": {"score": 0.8}}

        assert verdict(baseline, candidat, marge=0.05) == "amelioration"

    def test_regression(self):
        baseline = {"moyennes": {"score": 0.8}}
        candidat = {"moyennes": {"score": 0.5}}

        assert verdict(baseline, candidat, marge=0.05) == "regression"

    def test_indecis_sous_la_marge(self):
        baseline = {"moyennes": {"score": 0.80}}
        candidat = {"moyennes": {"score": 0.82}}

        assert verdict(baseline, candidat, marge=0.05) == "indecis"

    def test_leve_value_error_sur_cles_divergentes(self):
        baseline = {"moyennes": {"score_a": 0.8}}
        candidat = {"moyennes": {"score_b": 0.8}}

        with pytest.raises(ValueError):
            verdict(baseline, candidat, marge=0.05)


class TestExigerNonRegression:
    def test_leve_regression_error_sur_regression(self):
        baseline = {"moyennes": {"score": 0.8}}
        candidat = {"moyennes": {"score": 0.5}}

        with pytest.raises(RegressionError):
            exiger_non_regression(baseline, candidat, marge=0.05)

    @pytest.mark.parametrize(
        "candidat",
        [
            {"moyennes": {"score": 0.8}},
            {"moyennes": {"score": 0.82}},
            {"moyennes": {"score": 0.95}},
        ],
    )
    def test_ne_leve_rien_sinon(self, candidat: dict):
        baseline = {"moyennes": {"score": 0.8}}

        exiger_non_regression(baseline, candidat, marge=0.05)


class TestDataset:
    def test_au_moins_quinze_cas(self):
        assert len(CAS) >= 15

    def test_identifiants_uniques(self):
        identifiants = [cas.identifiant for cas in CAS]

        assert len(identifiants) == len(set(identifiants))

    def test_le_dataset_ne_cite_que_des_references_du_catalogue(self):
        from fabrique.mcp_catalogue import catalogue

        for cas in CAS:
            for ref in cas.attendus.get("refs_produit_attendues", []):
                assert catalogue.get(ref) is not None, ref
