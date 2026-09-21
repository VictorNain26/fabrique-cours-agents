"""Workflow Temporal deterministe : le chemin automatique de la fabrique.

Redaction -> controle -> correction -> redaction, borne a `max_tours`, puis
publication. Pas de validation humaine ici : c'est le role de LangGraph dans
ce projet (voir `fabrique.generation.graphe`), Temporal orchestre le chemin
automatique jusqu'a la publication.

Aucune route de l'API ne demarre ce workflow : il est exerce par
tests/test_temporal.py et par soumission manuelle au worker.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from fabrique.temporal.activites import controler_page, generer_page, publier_page

TIMEOUT_GENERATION = timedelta(seconds=60)
TIMEOUT_CONTROLE = timedelta(seconds=10)
TIMEOUT_PUBLICATION = timedelta(seconds=30)

RETRY_ACTIVITE = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)

# BudgetDepasse signale une enveloppe epuisee, pas un incident transitoire :
# la retenter ne fait que consommer un peu plus du budget deja depense.
RETRY_GENERATION = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_attempts=3,
    non_retryable_error_types=["BudgetDepasse"],
)


@workflow.defn
class GenerationPage:
    @workflow.run
    async def run(self, brief: str, pages_existantes: list[str]) -> dict:
        workflow.logger.info(f"demarrage: {workflow.now().isoformat()}")

        max_tours = 3
        retour: str | None = None
        page_json = ""
        violations: list[dict] = []
        bloquantes: list[dict] = []
        cout_total = 0.0

        for tour in range(1, max_tours + 1):
            workflow.logger.info(f"tour {tour}/{max_tours}")

            resultat_generation = await workflow.execute_activity(
                generer_page,
                args=[brief, retour, cout_total],
                start_to_close_timeout=TIMEOUT_GENERATION,
                retry_policy=RETRY_GENERATION,
            )
            page_json = resultat_generation["page"]
            cout_total += resultat_generation["cout"]

            violations = await workflow.execute_activity(
                controler_page,
                args=[page_json, pages_existantes],
                start_to_close_timeout=TIMEOUT_CONTROLE,
                retry_policy=RETRY_ACTIVITE,
            )

            bloquantes = [v for v in violations if v["gravite"] == "bloquant"]
            if not bloquantes:
                break

            retour = "retour_correction:\n" + "\n".join(
                f"- {v['code']}: {v['message']} {v['indice']}".rstrip() for v in bloquantes
            )

        if bloquantes:
            return {
                "page": page_json,
                "violations": violations,
                "publiee": False,
                "cout": cout_total,
            }

        cle_idempotence = str(workflow.uuid4())
        identifiant = await workflow.execute_activity(
            publier_page,
            args=[page_json, cle_idempotence],
            start_to_close_timeout=TIMEOUT_PUBLICATION,
            retry_policy=RETRY_ACTIVITE,
        )

        return {
            "page": page_json,
            "violations": violations,
            "publiee": True,
            "identifiant_publication": identifiant,
            "cout": cout_total,
        }
