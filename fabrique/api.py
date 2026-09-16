"""API HTTP de la fabrique : lancement de generation, lecture d'etat, validation
humaine. Frontiere : validation stricte des corps de requete et de reponse.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import ExitStack, asynccontextmanager
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from fabrique.config import reglages
from fabrique.generation.graphe import construire
from fabrique.generation.reprise import en_attente, reprendre
from fabrique.modeles import Page, Violation
from fabrique.providers.base import (
    BudgetDepasse,
    Fatale,
    SortieInvalide,
    Surcharge,
)
from fabrique.providers.chaine import chaine_depuis_reglages


class SanteReponse(BaseModel):
    statut: Literal["ok"]
    fournisseurs: list[str]


class CreerPageRequete(BaseModel):
    brief: str = Field(min_length=1)
    pages_existantes: list[str] = Field(default_factory=list)


class CreerPageReponse(BaseModel):
    thread_id: str
    statut: Literal["en_attente_validation", "terminee"]
    page: dict | None
    violations: list[Violation]
    # Qui a reellement repondu, et ce que la page a coute. Sans ces deux champs
    # cote HTTP, un repli reste invisible pour l'appelant.
    fournisseur: str | None = None
    cout: float | None = None


class EtatPageReponse(BaseModel):
    thread_id: str
    statut: Literal["en_attente_validation", "publiee", "refusee", "terminee"]
    page: dict | None
    violations: list[Violation]
    fournisseur: str | None = None
    cout: float | None = None


class ValidationRequete(BaseModel):
    approuve: bool
    commentaire: str = ""


class ValidationReponse(BaseModel):
    statut: Literal["publiee", "refusee"]
    page: dict | None
    identifiant_publication: str | None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    parametres = reglages()
    with ExitStack() as pile:
        if parametres.dsn:
            checkpointer = pile.enter_context(PostgresSaver.from_conn_string(parametres.dsn))
            checkpointer.setup()
        else:
            checkpointer = InMemorySaver()

        app.state.checkpointer = checkpointer
        app.state.fournisseurs = chaine_depuis_reglages(parametres)
        yield


app = FastAPI(lifespan=lifespan)


@app.exception_handler(BudgetDepasse)
async def _gerer_budget_depasse(request: Request, exc: BudgetDepasse) -> JSONResponse:
    return JSONResponse(status_code=402, content={"detail": str(exc)})


@app.exception_handler(Surcharge)
async def _gerer_surcharge(request: Request, exc: Surcharge) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(SortieInvalide)
async def _gerer_sortie_invalide(request: Request, exc: SortieInvalide) -> JSONResponse:
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(Fatale)
async def _gerer_fatale(request: Request, exc: Fatale) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


def _config(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _graphe(
    request: Request,
    pages_existantes: set[str],
    *,
    publier: Callable[[Page], str] | None = None,
) -> CompiledStateGraph:
    parametres = reglages()
    arguments = {
        "checkpointer": request.app.state.checkpointer,
        "max_tours": parametres.max_tours_correction,
        "budget_par_page": parametres.budget_par_page,
        "budget_tokens_invite": parametres.budget_tokens_invite,
    }
    if publier is not None:
        arguments["publier"] = publier
    return construire(request.app.state.fournisseurs, pages_existantes, **arguments)


def _statut_depuis_etat(etat) -> str:
    if etat.next == ("validation_humaine",):
        return "en_attente_validation"
    if etat.values.get("publiee"):
        return "publiee"
    if etat.values.get("approuve") is False:
        return "refusee"
    return "terminee"


@app.get("/sante")
def sante() -> SanteReponse:
    return SanteReponse(statut="ok", fournisseurs=reglages().chaine)


@app.post("/pages", status_code=202)
def creer_page(requete: CreerPageRequete, request: Request) -> CreerPageReponse:
    thread_id = str(uuid.uuid4())
    graphe = _graphe(request, set(requete.pages_existantes))

    resultat = graphe.invoke({"brief": requete.brief}, config=_config(thread_id))

    statut = "en_attente_validation" if "__interrupt__" in resultat else "terminee"
    return CreerPageReponse(
        thread_id=thread_id,
        statut=statut,
        page=resultat.get("page"),
        violations=[Violation.model_validate(v) for v in resultat.get("violations", [])],
        fournisseur=resultat.get("fournisseur"),
        cout=resultat.get("cout"),
    )


@app.get("/pages/{thread_id}")
def lire_page(thread_id: str, request: Request) -> EtatPageReponse:
    graphe = _graphe(request, set())
    etat = graphe.get_state(_config(thread_id))

    if not etat.values:
        raise HTTPException(status_code=404, detail="thread inconnu")

    return EtatPageReponse(
        thread_id=thread_id,
        statut=_statut_depuis_etat(etat),
        page=etat.values.get("page"),
        violations=[Violation.model_validate(v) for v in etat.values.get("violations", [])],
        fournisseur=etat.values.get("fournisseur"),
        cout=etat.values.get("cout"),
    )


@app.post("/pages/{thread_id}/validation")
def valider_page(thread_id: str, requete: ValidationRequete, request: Request) -> ValidationReponse:
    config = _config(thread_id)
    etat = _graphe(request, set()).get_state(config)

    if not etat.values:
        raise HTTPException(status_code=404, detail="thread inconnu")
    if not en_attente(_graphe(request, set()), config):
        raise HTTPException(status_code=409, detail="thread pas en attente de validation")

    identifiants: list[str] = []

    def publier(page: Page) -> str:
        identifiant = f"pub-{uuid.uuid4()}"
        identifiants.append(identifiant)
        return identifiant

    graphe = _graphe(request, set(), publier=publier)
    resultat = reprendre(graphe, config, approuve=requete.approuve, commentaire=requete.commentaire)

    if resultat.get("publiee"):
        return ValidationReponse(
            statut="publiee",
            page=resultat.get("page"),
            identifiant_publication=identifiants[0],
        )
    return ValidationReponse(
        statut="refusee", page=resultat.get("page"), identifiant_publication=None
    )
