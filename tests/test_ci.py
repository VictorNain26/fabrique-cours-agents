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
