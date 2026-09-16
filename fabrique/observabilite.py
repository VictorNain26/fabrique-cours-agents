"""Instrumentation Langfuse de la fabrique.

Sans cles configurees, `get_client()` renvoie un client desactive qui absorbe
tous les appels sans lever : ce module reste donc utilisable en local et en CI
sans compte Langfuse.
"""

from __future__ import annotations

from langfuse import get_client, observe

from fabrique.config import reglages
from fabrique.modeles import Violation

__all__ = ["actif", "observe", "tracer_violation", "vider"]


def actif() -> bool:
    parametres = reglages()
    return bool(parametres.langfuse_public_key and parametres.langfuse_secret_key)


def tracer_violation(v: Violation) -> None:
    """Enregistre une violation comme un score ancre dans une observation.

    Un score doit etre rattache a quelque chose : trace, observation, session ou
    dataset run. Sans ancrage, l'API le refuse en 400 alors que la signature du
    SDK presente tous ces champs comme optionnels.
    """
    if not actif():
        return

    client = get_client()
    with client.start_as_current_observation(as_type="guardrail", name=v.code) as span:
        span.update(metadata={"gravite": v.gravite, "indice": v.indice})
        client.create_score(
            name=v.code,
            value=1.0,
            data_type="BOOLEAN",
            comment=v.message,
            trace_id=client.get_current_trace_id(),
        )


def vider() -> None:
    get_client().flush()
