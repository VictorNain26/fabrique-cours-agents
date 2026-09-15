"""Contrats de donnees de la fabrique. Partages par tous les modules."""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict

from pydantic import BaseModel, Field

TypeBloc = Literal["titre", "paragraphe", "cta", "tableau_prix"]
Gravite = Literal["bloquant", "avertissement"]


class BlocPage(BaseModel):
    type: TypeBloc
    contenu: str = Field(max_length=200)
    # Le validateur interdit les prix en dur : un tableau de prix designe un
    # produit du catalogue, et le prix reel est resolu ensuite via MCP.
    product_ref: str | None = None


class Page(BaseModel):
    titre_h1: str = Field(max_length=70)
    meta_description: str = Field(min_length=120, max_length=158)
    blocs: list[BlocPage] = Field(min_length=1)
    liens: list[str] = Field(default_factory=list)


class Violation(BaseModel):
    code: str
    gravite: Gravite
    message: str
    indice: str = ""


class EtatPage(TypedDict, total=False):
    """Etat du graphe LangGraph. Les cles absentes valent leur defaut."""

    brief: str
    page: dict | None
    violations: list[dict]
    essais: int
    journal: Annotated[list[str], lambda a, b: (a or []) + (b or [])]
    approuve: bool | None
    commentaire_humain: str
    publiee: bool
