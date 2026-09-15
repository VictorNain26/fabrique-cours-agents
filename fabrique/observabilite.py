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
    if not actif():
        return

    get_client().create_score(
        name=v.code,
        value=1.0,
        data_type="BOOLEAN",
        comment=v.message,
    )


def vider() -> None:
    get_client().flush()
