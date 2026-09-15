"""Politique de repli entre fournisseurs, sous enveloppe budgetaire.

Chapitre 8 : une categorie d'erreur, une strategie (voir base.py).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from fabrique.providers.base import BudgetDepasse, Fatale, Fournisseur, SortieInvalide, Surcharge

T = TypeVar("T")


@dataclass(frozen=True)
class Resultat:
    valeur: T
    # Le nom du fournisseur qui a reellement repondu doit remonter : un repli
    # silencieux fausse toute evaluation ulterieure (quel fournisseur a produit
    # quoi).
    fournisseur: str
    cout: float
    essais: int


def executer(
    fournisseurs: list[Fournisseur],
    budget: float,
    appel: Callable[[Fournisseur], T],
) -> Resultat[T]:
    restant = budget
    essais = 0
    cout_cumule = 0.0

    for fournisseur in fournisseurs:
        reessai_disponible = True
        while True:
            if fournisseur.cout_par_appel > restant:
                raise BudgetDepasse(
                    f"budget insuffisant pour {fournisseur.nom} "
                    f"(reste {restant}, requis {fournisseur.cout_par_appel})"
                )
            restant -= fournisseur.cout_par_appel
            cout_cumule += fournisseur.cout_par_appel
            essais += 1

            try:
                valeur = appel(fournisseur)
            except Fatale:
                raise
            except Surcharge:
                break
            except SortieInvalide:
                if reessai_disponible:
                    reessai_disponible = False
                    continue
                break
            else:
                return Resultat(
                    valeur=valeur,
                    fournisseur=fournisseur.nom,
                    cout=cout_cumule,
                    essais=essais,
                )

    raise Surcharge("tous les fournisseurs sont epuises")
