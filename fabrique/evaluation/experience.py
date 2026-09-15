"""Harnais d'evaluation : execution locale (CI, sans reseau) et via Langfuse."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from statistics import mean
from typing import Any

from langfuse import Evaluation, RegressionError, get_client
from langfuse.experiment import ExperimentResult

from fabrique.evaluation.dataset import CAS, CasGolden
from fabrique.evaluation.evaluateurs import (
    refs_produit_resolues,
    respecte_longueurs,
    sans_violation_bloquante,
)

Tache = Callable[..., Any]
FonctionEvaluateur = Callable[..., Evaluation | list[Evaluation]]

EVALUATEURS_PAR_DEFAUT: list[FonctionEvaluateur] = [
    sans_violation_bloquante,
    respecte_longueurs,
    refs_produit_resolues,
]


def _item_de(cas: CasGolden) -> dict[str, Any]:
    return {
        "input": cas.brief,
        "expected_output": cas.attendus,
        "metadata": {
            "identifiant": cas.identifiant,
            "pages_existantes": sorted(cas.pages_existantes),
        },
    }


def _evaluations(resultat: Evaluation | list[Evaluation]) -> list[Evaluation]:
    return resultat if isinstance(resultat, list) else [resultat]


def lancer_local(
    task: Tache,
    cas: list[CasGolden] = CAS,
    evaluateurs: list[FonctionEvaluateur] = EVALUATEURS_PAR_DEFAUT,
) -> dict[str, Any]:
    scores: dict[str, list[float]] = defaultdict(list)
    detail: list[dict[str, Any]] = []

    for un_cas in cas:
        item = _item_de(un_cas)
        sortie = task(item=item)
        evaluations = [
            evaluation
            for evaluateur in evaluateurs
            for evaluation in _evaluations(
                evaluateur(
                    input=item["input"],
                    output=sortie,
                    expected_output=item["expected_output"],
                    metadata=item["metadata"],
                )
            )
        ]
        for evaluation in evaluations:
            if isinstance(evaluation.value, (int, float)):
                scores[evaluation.name].append(float(evaluation.value))

        detail.append(
            {"identifiant": un_cas.identifiant, "sortie": sortie, "evaluations": evaluations}
        )

    moyennes = {nom: mean(valeurs) for nom, valeurs in scores.items()}
    return {"moyennes": moyennes, "detail": detail}


def lancer_langfuse(
    task: Tache,
    cas: list[CasGolden] = CAS,
    evaluateurs: list[FonctionEvaluateur] = EVALUATEURS_PAR_DEFAUT,
    nom: str = "fabrique-golden-dataset",
) -> dict[str, Any]:
    resultat = get_client().run_experiment(
        name=nom,
        data=[_item_de(un_cas) for un_cas in cas],
        task=task,
        evaluators=evaluateurs,
    )

    scores: dict[str, list[float]] = defaultdict(list)
    for item_resultat in resultat.item_results:
        for evaluation in item_resultat.evaluations:
            if isinstance(evaluation.value, (int, float)):
                scores[evaluation.name].append(float(evaluation.value))

    return {
        "moyennes": {nom: mean(valeurs) for nom, valeurs in scores.items()},
        "resultat": resultat,
    }


def verdict(baseline: dict[str, Any], candidat: dict[str, Any], marge: float) -> str:
    cles_baseline = set(baseline["moyennes"])
    cles_candidat = set(candidat["moyennes"])
    if cles_baseline != cles_candidat:
        raise ValueError(
            f"Jeux de scores differents : baseline={sorted(cles_baseline)}, candidat={sorted(cles_candidat)}"
        )

    ecarts = {nom: candidat["moyennes"][nom] - baseline["moyennes"][nom] for nom in cles_baseline}

    if any(ecart < -marge for ecart in ecarts.values()):
        return "regression"
    if any(ecart > marge for ecart in ecarts.values()):
        return "amelioration"

    # "indecis" est une reponse de plein droit : sur un petit dataset, un ecart
    # sous la marge est du bruit statistique, et conclure dessus est l'erreur
    # classique.
    return "indecis"


def exiger_non_regression(baseline: dict[str, Any], candidat: dict[str, Any], marge: float) -> None:
    if verdict(baseline, candidat, marge) != "regression":
        return

    pire_metrique = min(
        baseline["moyennes"],
        key=lambda nom: candidat["moyennes"][nom] - baseline["moyennes"][nom],
    )
    resultat = ExperimentResult(
        name="fabrique-golden-dataset",
        run_name="local",
        description=None,
        item_results=[],
        run_evaluations=[
            Evaluation(name=nom, value=valeur) for nom, valeur in candidat["moyennes"].items()
        ],
        experiment_id="local",
    )
    raise RegressionError(
        result=resultat,
        metric=pire_metrique,
        value=candidat["moyennes"][pire_metrique],
        threshold=baseline["moyennes"][pire_metrique] - marge,
    )
