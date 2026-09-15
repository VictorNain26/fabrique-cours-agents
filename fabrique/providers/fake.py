"""Fournisseur fake, deterministe et sans reseau. Utilise par les tests et la CI."""

from __future__ import annotations

import json
from enum import Enum
from types import UnionType
from typing import Any, Literal, Union, get_args, get_origin

import annotated_types
from pydantic import BaseModel
from pydantic.fields import FieldInfo

from .base import ErreurFournisseur, Reponse


def _valeur_exemple(annotation: Any) -> Any:
    origine = get_origin(annotation)

    if origine in (Union, UnionType):
        options = [a for a in get_args(annotation) if a is not type(None)]
        return _valeur_exemple(options[0]) if options else None

    if origine is Literal:
        return get_args(annotation)[0]

    if origine in (list, tuple, set):
        args = get_args(annotation)
        return [_valeur_exemple(args[0])] if args else []

    if origine is dict:
        return {}

    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return _instance_exemple(annotation)

    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return next(iter(annotation)).value

    if annotation is str:
        return "exemple"
    if annotation is int:
        return 0
    if annotation is float:
        return 0.0
    if annotation is bool:
        return False

    return None


def _valeur_champ(champ: FieldInfo) -> Any:
    valeur = _valeur_exemple(champ.annotation)

    for contrainte in champ.metadata:
        if isinstance(contrainte, annotated_types.MinLen):
            if isinstance(valeur, str) and len(valeur) < contrainte.min_length:
                valeur = valeur.ljust(contrainte.min_length, "x")
            elif isinstance(valeur, list):
                args = get_args(champ.annotation)
                remplissage = valeur[0] if valeur else _valeur_exemple(args[0] if args else None)
                while len(valeur) < contrainte.min_length:
                    valeur.append(remplissage)
        if isinstance(contrainte, annotated_types.MaxLen) and isinstance(valeur, str):
            valeur = valeur[: contrainte.max_length]

    return valeur


def _instance_exemple(schema: type[BaseModel]) -> dict[str, Any]:
    return {nom: _valeur_champ(champ) for nom, champ in schema.model_fields.items()}


def _json_exemple(schema: type[BaseModel]) -> str:
    return json.dumps(_instance_exemple(schema))


class FournisseurFake:
    """Fournisseur scriptable : sert des reponses et des erreurs dans l'ordre fourni.

    Quand la liste de reponses (ou d'erreurs) est epuisee, le dernier element
    est rejoue pour les appels suivants.
    """

    nom = "fake"
    cout_par_appel = 0.0

    def __init__(
        self,
        reponses: list[str] | None = None,
        erreurs: list[ErreurFournisseur | None] | None = None,
    ) -> None:
        self.reponses = reponses or []
        self.erreurs = erreurs or []
        self.appels: list[dict[str, Any]] = []

    def generer(
        self,
        *,
        invite: str,
        schema: type[BaseModel],
        systeme: str = "",
        retour: str | None = None,
    ) -> Reponse:
        self.appels.append({"invite": invite, "retour": retour})
        index = len(self.appels) - 1

        if self.erreurs:
            erreur = self.erreurs[min(index, len(self.erreurs) - 1)]
            if erreur is not None:
                raise erreur

        if self.reponses:
            texte = self.reponses[min(index, len(self.reponses) - 1)]
        else:
            texte = _json_exemple(schema)

        return Reponse(texte=texte, modele=self.nom)
