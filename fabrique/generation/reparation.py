"""Boucle de reparation bornee : reinjecte l'erreur de validation au fournisseur."""

from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from fabrique.providers.base import Fournisseur, SortieInvalide

M = TypeVar("M", bound=BaseModel)


def message_de_reparation(e: ValidationError) -> str:
    lignes = [f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}" for err in e.errors()]
    return "\n".join(lignes)


def generer_valide(
    fournisseur: Fournisseur,
    *,
    invite: str,
    schema: type[M],
    systeme: str = "",
    max_essais: int = 2,
) -> M:
    retour: str | None = None
    derniere_erreur: ValidationError | None = None

    for _ in range(max_essais):
        reponse = fournisseur.generer(
            invite=invite,
            schema=schema,
            systeme=systeme,
            retour=retour,
        )
        try:
            return schema.model_validate_json(reponse.texte)
        except ValidationError as e:
            derniere_erreur = e
            retour = message_de_reparation(e)

    raise SortieInvalide(f"sortie invalide apres {max_essais} essais") from derniere_erreur
