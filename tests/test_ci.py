"""Porte de non-regression : une reference absente ne doit pas passer en silence."""

from __future__ import annotations

import json

import pytest

from fabrique.evaluation import ci

MOYENNES = {"sans_violation_bloquante": 1.0}


@pytest.fixture
def reference(tmp_path, monkeypatch):
    chemin = tmp_path / "reference.json"
    monkeypatch.setattr(ci, "REFERENCE", chemin)
    monkeypatch.setattr(ci, "lancer_local", lambda *_: {"moyennes": dict(MOYENNES)})
    return chemin


def test_reference_absente_fait_echouer_la_porte(reference):
    assert ci.main([]) == 1
    assert not reference.exists()


def test_ecrire_reference_la_cree_explicitement(reference):
    assert ci.main(["--ecrire-reference"]) == 0
    assert json.loads(reference.read_text()) == {"moyennes": MOYENNES}


def test_reference_presente_et_identique_passe(reference):
    reference.write_text(json.dumps({"moyennes": MOYENNES}))
    assert ci.main([]) == 0


def test_reference_versionnee_existe():
    assert ci.REFERENCE.exists()


def test_la_porte_exerce_la_tarification_quand_le_cas_attend_des_refs():
    from fabrique.evaluation.dataset import CAS
    from fabrique.evaluation.experience import _item_de

    cas = next(c for c in CAS if c.attendus.get("refs_produit_attendues"))
    reference = cas.attendus["refs_produit_attendues"][0]

    page = ci.tache(item=_item_de(cas))

    tableaux = [b for b in page["blocs"] if b["type"] == "tableau_prix"]
    assert [b["product_ref"] for b in tableaux] == [reference]
    assert tableaux[0]["prix_affiche"].endswith("EUR / mois")
