"""Instrumentation Langfuse de la fabrique.

Sans cles configurees, `actif()` court-circuite tout avant `get_client()` : ce
module reste utilisable en local et en CI sans compte Langfuse. Le SDK se
desactive seul quand LANGFUSE_PUBLIC_KEY est absente, mais une variable
presente et vide (celle de `.env.exemple`, reprise par docker compose) lui
suffit pour ouvrir un exporteur : d'ou ce garde-fou, verifie par execution sur
langfuse 4.15.3.

Forme d'une trace de page : une trace par thread_id, un span par noeud du
graphe, un span par essai de la chaine de repli, une observation `generation`
par appel fournisseur (modele, tokens, cout quand il est connu).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager, nullcontext
from typing import Any

from langfuse import get_client, observe, propagate_attributes

from fabrique.config import reglages
from fabrique.modeles import Violation

__all__ = ["actif", "observation", "observe", "tracer_violation", "vider"]

NOM_TRACE = "page"


def actif() -> bool:
    parametres = reglages()
    return bool(parametres.langfuse_public_key and parametres.langfuse_secret_key)


def _rien(**_: Any) -> None:
    return None


@contextmanager
def observation(
    nom: str,
    *,
    as_type: str = "span",
    fil: str | None = None,
    **attributs: Any,
) -> Iterator[Callable[..., None]]:
    """Ouvre une observation courante et rend de quoi la mettre a jour.

    `fil` derive l'identifiant de trace du thread_id LangGraph : la reprise
    apres validation humaine est un second `invoke`, et sans cette graine elle
    ouvrirait une seconde trace pour la meme page.

    Une exception est notee en niveau ERROR puis propagee : la chaine de repli
    doit rester lisible dans la trace, pas seulement dans les journaux.
    """
    if not actif():
        yield _rien
        return

    client = get_client()
    contexte = {"trace_id": client.create_trace_id(seed=fil)} if fil else None
    propagation = (
        propagate_attributes(trace_name=NOM_TRACE, session_id=fil) if fil else nullcontext()
    )
    with (
        client.start_as_current_observation(
            name=nom, as_type=as_type, trace_context=contexte, **attributs
        ) as obs,
        propagation,
    ):
        try:
            yield obs.update
        except Exception as erreur:
            obs.update(level="ERROR", status_message=f"{type(erreur).__name__}: {erreur}")
            raise


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
