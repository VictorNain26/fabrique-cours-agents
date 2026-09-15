"""Contrat fournisseur LLM et taxonomie d'erreurs.

La taxonomie est le socle du chapitre 8 : une categorie d'erreur, une strategie.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import BaseModel


class ErreurFournisseur(Exception):
    """Racine commune, pour attraper large quand c'est justifie."""


class Surcharge(ErreurFournisseur):
    """429, rate limit, indisponibilite passagere. Repli sur un autre fournisseur."""


class SortieInvalide(ErreurFournisseur):
    """Le texte renvoye ne respecte pas le schema. Un seul re-essai, avec l'erreur."""


class Fatale(ErreurFournisseur):
    """Cle invalide, modele inexistant, refus. Aucun re-essai."""


class BudgetDepasse(ErreurFournisseur):
    """Le cout de l'essai suivant depasse l'enveloppe autorisee."""


@dataclass(frozen=True)
class Reponse:
    texte: str
    modele: str
    tokens_entree: int = 0
    tokens_sortie: int = 0

    @property
    def tokens(self) -> int:
        return self.tokens_entree + self.tokens_sortie


@runtime_checkable
class Fournisseur(Protocol):
    """Un fournisseur sait produire du texte contraint par un schema Pydantic.

    `retour` porte l'erreur de validation de l'essai precedent ; il vaut None au
    premier essai. Les implementations traduisent leurs erreurs natives vers la
    taxonomie ci-dessus : c'est la frontiere ou la validation est stricte.
    """

    nom: str
    cout_par_appel: float

    def generer(
        self,
        *,
        invite: str,
        schema: type[BaseModel],
        systeme: str = "",
        retour: str | None = None,
    ) -> Reponse: ...
