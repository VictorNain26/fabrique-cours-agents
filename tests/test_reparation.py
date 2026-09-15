from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import BaseModel, ValidationError

from fabrique.generation.reparation import generer_valide, message_de_reparation
from fabrique.providers.base import Reponse, SortieInvalide


class SchemaBidon(BaseModel):
    nom: str
    age: int


@dataclass
class FournisseurDouble:
    nom: str
    cout_par_appel: float
    textes: list[str]
    retours_recus: list[str | None] = field(default_factory=list)

    def generer(self, *, invite, schema, systeme="", retour=None):
        self.retours_recus.append(retour)
        index = len(self.retours_recus) - 1
        return Reponse(texte=self.textes[index], modele=self.nom)


def test_validation_reussie_au_premier_coup():
    f = FournisseurDouble(nom="a", cout_par_appel=0.1, textes=['{"nom": "Ada", "age": 30}'])

    resultat = generer_valide(f, invite="x", schema=SchemaBidon)

    assert resultat == SchemaBidon(nom="Ada", age=30)
    assert len(f.retours_recus) == 1
    assert f.retours_recus[0] is None


def test_reparation_au_deuxieme_essai():
    f = FournisseurDouble(
        nom="a",
        cout_par_appel=0.1,
        textes=['{"nom": "Ada"}', '{"nom": "Ada", "age": 30}'],
    )

    resultat = generer_valide(f, invite="x", schema=SchemaBidon)

    assert resultat == SchemaBidon(nom="Ada", age=30)
    assert len(f.retours_recus) == 2


def test_retour_contient_le_champ_fautif():
    f = FournisseurDouble(
        nom="a",
        cout_par_appel=0.1,
        textes=['{"nom": "Ada"}', '{"nom": "Ada", "age": 30}'],
    )

    generer_valide(f, invite="x", schema=SchemaBidon)

    assert f.retours_recus[0] is None
    assert "age" in f.retours_recus[1]


def test_sortie_invalide_apres_epuisement_avec_cause():
    f = FournisseurDouble(
        nom="a",
        cout_par_appel=0.1,
        textes=['{"nom": "Ada"}', '{"nom": "Ada"}'],
    )

    with pytest.raises(SortieInvalide) as exc_info:
        generer_valide(f, invite="x", schema=SchemaBidon, max_essais=2)

    assert isinstance(exc_info.value.__cause__, ValidationError)


def test_borne_respectee_nombre_exact_appels():
    f = FournisseurDouble(
        nom="a",
        cout_par_appel=0.1,
        textes=['{"nom": "Ada"}', '{"nom": "Ada"}', '{"nom": "Ada", "age": 30}'],
    )

    with pytest.raises(SortieInvalide):
        generer_valide(f, invite="x", schema=SchemaBidon, max_essais=2)

    assert len(f.retours_recus) == 2


def test_message_de_reparation_compact_avec_chemin():
    try:
        SchemaBidon.model_validate_json('{"nom": "Ada"}')
    except ValidationError as e:
        message = message_de_reparation(e)

    assert "age" in message
