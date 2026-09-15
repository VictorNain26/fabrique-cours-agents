"""Detection et reprise d'une execution suspendue en attente de validation humaine.

Formes observees sur langgraph 1.2.11, verifiees par execution :
  - invoke() sur un graphe qui s'interrompt renvoie un etat portant la cle
    "__interrupt__", un tuple d'objets Interrupt(value=..., id=...)
  - get_state(config).next donne les noeuds en attente, ex ("validation_humaine",)
  - la reprise passe par invoke(Command(resume=...), config)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.types import Command


@dataclass(frozen=True)
class Interruption:
    noeud: str
    charge: Any


def interruption(etat: dict, graphe, config: dict) -> Interruption | None:
    """Renvoie l'interruption en cours, ou None si l'execution est terminee."""
    brutes = etat.get("__interrupt__")
    if not brutes:
        return None
    instantane = graphe.get_state(config)
    noeud = instantane.next[0] if instantane.next else ""
    return Interruption(noeud=noeud, charge=brutes[0].value)


def en_attente(graphe, config: dict) -> bool:
    return bool(graphe.get_state(config).next)


def reprendre(graphe, config: dict, *, approuve: bool, commentaire: str = "") -> dict:
    """Rend la main au graphe avec la decision humaine.

    La valeur passee a resume est exactement ce que interrupt() renvoie dans le
    noeud suspendu : le contrat entre l'appelant HTTP et le graphe tient ici.
    """
    return graphe.invoke(
        Command(resume={"approuve": approuve, "commentaire": commentaire}),
        config=config,
    )
