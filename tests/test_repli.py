from __future__ import annotations

from dataclasses import dataclass, field

import pytest
from pydantic import BaseModel

from fabrique.providers.base import BudgetDepasse, Fatale, Reponse, SortieInvalide, Surcharge
from fabrique.providers.repli import executer


class SchemaBidon(BaseModel):
    valeur: str


@dataclass
class FournisseurDouble:
    nom: str
    cout_par_appel: float
    comportements: list[type[Exception] | None] = field(default_factory=list)
    appels: list[str | None] = field(default_factory=list)

    def generer(self, *, invite, schema, systeme="", retour=None):
        self.appels.append(retour)
        index = len(self.appels) - 1
        comportement = self.comportements[index]
        if comportement is not None:
            raise comportement(f"{self.nom} erreur")
        return Reponse(texte="ok", modele=self.nom)


def appel(fournisseur):
    return fournisseur.generer(invite="x", schema=SchemaBidon)


def test_cas_nominal():
    f = FournisseurDouble(nom="a", cout_par_appel=0.1, comportements=[None])

    resultat = executer([f], budget=1.0, appel=appel)

    assert resultat.valeur.texte == "ok"
    assert resultat.fournisseur == "a"
    assert resultat.cout == 0.1
    assert resultat.essais == 1
    assert len(f.appels) == 1


def test_cout_compte_sur_plusieurs_fournisseurs():
    a = FournisseurDouble(nom="a", cout_par_appel=0.2, comportements=[Surcharge])
    b = FournisseurDouble(nom="b", cout_par_appel=0.3, comportements=[None])

    resultat = executer([a, b], budget=1.0, appel=appel)

    assert resultat.fournisseur == "b"
    assert resultat.cout == pytest.approx(0.5)
    assert resultat.essais == 2


def test_surcharge_bascule_sans_second_essai():
    a = FournisseurDouble(nom="a", cout_par_appel=0.1, comportements=[Surcharge, None])
    b = FournisseurDouble(nom="b", cout_par_appel=0.1, comportements=[None])

    resultat = executer([a, b], budget=1.0, appel=appel)

    assert resultat.fournisseur == "b"
    assert len(a.appels) == 1
    assert len(b.appels) == 1


def test_sortie_invalide_un_seul_reessai():
    a = FournisseurDouble(nom="a", cout_par_appel=0.1, comportements=[SortieInvalide, None])

    resultat = executer([a], budget=1.0, appel=appel)

    assert resultat.fournisseur == "a"
    assert resultat.essais == 2
    assert len(a.appels) == 2


def test_sortie_invalide_pas_de_reessai_infini():
    a = FournisseurDouble(
        nom="a", cout_par_appel=0.1, comportements=[SortieInvalide, SortieInvalide]
    )
    b = FournisseurDouble(nom="b", cout_par_appel=0.1, comportements=[None])

    resultat = executer([a, b], budget=1.0, appel=appel)

    assert len(a.appels) == 2
    assert resultat.fournisseur == "b"


def test_fatale_arrete_tout_sans_repli():
    a = FournisseurDouble(nom="a", cout_par_appel=0.1, comportements=[Fatale])
    b = FournisseurDouble(nom="b", cout_par_appel=0.1, comportements=[None])

    with pytest.raises(Fatale):
        executer([a, b], budget=1.0, appel=appel)

    assert len(a.appels) == 1
    assert len(b.appels) == 0


def test_budget_depasse_verifie_avant_appel():
    a = FournisseurDouble(nom="a", cout_par_appel=1.0, comportements=[None])

    with pytest.raises(BudgetDepasse):
        executer([a], budget=0.5, appel=appel)

    assert len(a.appels) == 0


def test_tous_fournisseurs_epuises_leve_surcharge():
    a = FournisseurDouble(nom="a", cout_par_appel=0.1, comportements=[Surcharge])
    b = FournisseurDouble(
        nom="b", cout_par_appel=0.1, comportements=[SortieInvalide, SortieInvalide]
    )

    with pytest.raises(Surcharge):
        executer([a, b], budget=1.0, appel=appel)
