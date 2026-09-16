"""Structures de données du cours. Aucune dépendance externe."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class Source:
    """Une référence documentaire.

    niveau :
      "doc"       page officielle lue intégralement le 15/09/2026
      "recherche" extrait de page officielle vu via moteur de recherche
      "execute"   comportement vérifié en exécutant le code dans le venv du cours
      "auteur"    position de l'auteur du cours, pas une citation
    """

    niveau: str
    titre: str
    url: str = ""


@dataclass
class Bloc:
    kind: str  # "texte" | "code" | "titre" | "alerte"
    contenu: str


@dataclass
class Question:
    enonce: str
    options: list[str]
    bonne: int
    explication: str
    source: str = ""


@dataclass
class Kata:
    """Un atelier.

    `module` designe le vrai module de l'app (ex "fabrique.garde_fous.validateur").
    Ouvrir l'atelier met ce module de cote et le remplace par le squelette : ce que
    tu ecris est le code qui tourne en production, pas un fichier jetable. Le module
    est restaure a la sortie de l'atelier.

    `fichier` reste utilise pour les rares katas sans contrepartie dans l'app.
    """

    consigne: str
    squelette: str
    verifier: Callable[[object], list[tuple[bool, str]]]
    module: str = ""
    fichier: str = ""
    indice: str = ""
    solution: str = ""
    dependances: list[str] = field(default_factory=list)


@dataclass
class Chapitre:
    numero: int
    titre: str
    objectif: str
    duree_min: int
    blocs: list[Bloc] = field(default_factory=list)
    questions: list[Question] = field(default_factory=list)
    kata: Kata | None = None
    a_retenir: list[str] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
