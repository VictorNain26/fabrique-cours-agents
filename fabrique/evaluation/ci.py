"""Porte de non-regression appelee par l'integration continue.

Rejoue le golden dataset avec le fournisseur factice, compare les scores a la
reference versionnee dans le depot, et sort en erreur si la qualite recule.

Une reference absente fait echouer la porte : sinon, un run qui l'ecrit lui-meme
passe toujours. `--ecrire-reference` la (re)ecrit volontairement depuis ce run.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from fabrique.evaluation.dataset import CAS
from fabrique.evaluation.experience import exiger_non_regression, lancer_local
from fabrique.generation.graphe import construire
from fabrique.providers.fake import FournisseurFake

REFERENCE = Path(__file__).parent / "reference.json"
MARGE = 0.05


def tache(*, item, **_):
    graphe = construire(
        [FournisseurFake()],
        set(item["metadata"].get("pages_existantes", [])),
        checkpointer=InMemorySaver(),
    )
    config = {"configurable": {"thread_id": item["metadata"]["identifiant"]}}
    etat = graphe.invoke({"brief": item["input"], "essais": 0}, config=config)
    return etat.get("page")


def main(argv: Sequence[str] = ()) -> int:
    parser = argparse.ArgumentParser(prog="python -m fabrique.evaluation.ci")
    parser.add_argument(
        "--ecrire-reference",
        action="store_true",
        help="ecrit reference.json depuis ce run au lieu de comparer",
    )
    ecrire = parser.parse_args(list(argv)).ecrire_reference

    if not ecrire and not REFERENCE.exists():
        print(f"reference absente : {REFERENCE}")
        print("cree-la avec python -m fabrique.evaluation.ci --ecrire-reference")
        return 1

    candidat = {"moyennes": lancer_local(tache, CAS)["moyennes"]}

    if ecrire:
        REFERENCE.write_text(json.dumps(candidat, indent=2, sort_keys=True) + "\n")
        print(f"reference ecrite depuis ce run : {REFERENCE.name}")
        for nom, valeur in sorted(candidat["moyennes"].items()):
            print(f"  {nom:<28} {valeur:.3f}")
        return 0

    reference = json.loads(REFERENCE.read_text())
    print("evaluateur                     reference  candidat")
    for nom in sorted(set(reference["moyennes"]) | set(candidat["moyennes"])):
        print(
            f"  {nom:<28} {reference['moyennes'].get(nom, 0):>9.3f}"
            f"  {candidat['moyennes'].get(nom, 0):>8.3f}"
        )

    exiger_non_regression(reference, candidat, MARGE)
    print(f"\npas de regression au-dela de la marge de {MARGE}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
