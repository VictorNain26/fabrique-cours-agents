"""Activities Temporal : tout le travail non deterministe (LLM, reseau) vit ici.

Le workflow ne fait qu'orchestrer ces appels ; voir `fabrique.temporal.workflows`.
"""

from __future__ import annotations

from temporalio import activity

from fabrique.config import reglages
from fabrique.garde_fous.validateur import valider
from fabrique.generation.reparation import generer_valide
from fabrique.modeles import Page
from fabrique.providers.chaine import chaine_depuis_reglages
from fabrique.providers.repli import executer

SYSTEME = "Tu generes une page web au format JSON strict conforme au schema fourni."


@activity.defn
async def generer_page(brief: str, retour: str | None) -> str:
    parametres = reglages()
    fournisseurs = chaine_depuis_reglages(parametres)
    invite = brief if retour is None else f"{brief}\n\n{retour}"

    resultat = executer(
        fournisseurs,
        parametres.budget_par_page,
        lambda f: generer_valide(
            f,
            invite=invite,
            schema=Page,
            systeme=SYSTEME,
            max_essais=parametres.max_essais_reparation,
        ),
    )
    return resultat.valeur.model_dump_json()


@activity.defn
async def controler_page(page_json: str, pages_existantes: list[str]) -> list[dict]:
    page = Page.model_validate_json(page_json)
    violations = valider(page, set(pages_existantes))
    return [v.model_dump() for v in violations]


# Idempotence de publier_page : une activity retentee (timeout reseau, worker
# redemarre avant l'ack) peut s'executer deux fois pour le meme appel logique.
# Ce dict en memoire, cle par l'idempotence fournie par le workflow, garantit
# qu'une meme cle ne republie jamais.
_PUBLICATIONS: dict[str, str] = {}


@activity.defn
async def publier_page(page_json: str, cle_idempotence: str) -> str:
    if cle_idempotence in _PUBLICATIONS:
        return _PUBLICATIONS[cle_idempotence]
    identifiant = f"pub-{cle_idempotence}"
    _PUBLICATIONS[cle_idempotence] = identifiant
    return identifiant
