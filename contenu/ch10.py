from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

SQ10 = """
\"\"\"API HTTP de la fabrique : lancement de generation, lecture d'etat, validation
humaine. Frontiere : validation stricte des corps de requete et de reponse.
\"\"\"

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

from fabrique.config import Reglages, reglages
from fabrique.generation.graphe import construire
from fabrique.generation.reprise import en_attente, reprendre
from fabrique.modeles import Page, Violation
from fabrique.providers.anthropic import FournisseurAnthropic
from fabrique.providers.base import (
    BudgetDepasse,
    Fatale,
    Fournisseur,
    SortieInvalide,
    Surcharge,
)
from fabrique.providers.fake import FournisseurFake
from fabrique.providers.ovhcloud import FournisseurOVHcloud


class SanteReponse(BaseModel):
    statut: Literal["ok"]
    fournisseur: str


class CreerPageRequete(BaseModel):
    brief: str = Field(min_length=1)
    pages_existantes: list[str] = Field(default_factory=list)


class CreerPageReponse(BaseModel):
    thread_id: str
    statut: Literal["en_attente_validation", "terminee"]
    page: dict | None
    violations: list[Violation]


class EtatPageReponse(BaseModel):
    thread_id: str
    statut: Literal["en_attente_validation", "publiee", "refusee", "terminee"]
    page: dict | None
    violations: list[Violation]


class ValidationRequete(BaseModel):
    approuve: bool
    commentaire: str = ""


class ValidationReponse(BaseModel):
    statut: Literal["publiee", "refusee"]
    page: dict | None
    identifiant_publication: str | None


def _fournisseur_depuis_reglages(parametres: Reglages) -> Fournisseur:
    if parametres.fournisseur == "ovhcloud":
        return FournisseurOVHcloud(
            api_key=parametres.ovh_api_key,
            base_url=parametres.ovh_base_url,
            modele=parametres.ovh_modele,
        )
    if parametres.fournisseur == "anthropic":
        return FournisseurAnthropic(
            api_key=parametres.anthropic_api_key,
            modele=parametres.anthropic_modele,
        )
    return FournisseurFake()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    parametres = reglages()
    with ExitStack() as pile:
        if parametres.database_url:
            checkpointer = pile.enter_context(
                PostgresSaver.from_conn_string(parametres.database_url)
            )
            checkpointer.setup()
        else:
            checkpointer = InMemorySaver()

        app.state.checkpointer = checkpointer
        app.state.fournisseur = _fournisseur_depuis_reglages(parametres)
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
async def sante() -> SanteReponse:
    # Renvoie {"statut": "ok", "fournisseur": <nom>}.
    # Le HEALTHCHECK du Dockerfile tape ce chemin : ne le renomme pas.
    raise NotImplementedError


@app.post("/pages", status_code=202)
async def creer_page(requete: CreerPageRequete, request: Request) -> CreerPageReponse:
    # Genere un thread_id, construit le graphe, invoke avec le brief.
    # statut = "en_attente_validation" si la cle "__interrupt__" est
    # presente dans le resultat, "terminee" sinon.
    raise NotImplementedError


@app.get("/pages/{thread_id}")
async def lire_page(thread_id: str, request: Request) -> EtatPageReponse:
    # Lit l'etat via graphe.get_state(config).
    # 404 si le thread est inconnu : un thread jamais invoque renvoie
    # un instantane dont .values est vide, sans lever.
    raise NotImplementedError


@app.post("/pages/{thread_id}/validation")
async def valider_page(
    thread_id: str, requete: ValidationRequete, request: Request
) -> ValidationReponse:
    # 404 si thread inconnu, 409 s'il n'est pas en attente de validation.
    # Reprend via fabrique.generation.reprise.reprendre(...).
    # Renvoie publiee + identifiant, ou refusee.
    raise NotImplementedError
"""


def verif10(m):
    from fastapi.testclient import TestClient

    from fabrique.config import reglages

    app = ok(m, "app")
    res = []

    import os

    os.environ["FOURNISSEUR"] = "fake"
    os.environ["POSTGRES_HOST"] = ""
    reglages.cache_clear()

    with TestClient(app) as client:
        r = client.get("/sante")
        res.append((r.status_code == 200, f"GET /sante repond 200 (recu {r.status_code})"))
        res.append((r.json().get("statut") == "ok", "sante renvoie statut ok"))

        r = client.post("/pages", json={"brief": "page vps", "pages_existantes": ["/vps"]})
        res.append((r.status_code in (200, 202), f"POST /pages accepte (recu {r.status_code})"))
        corps = r.json()
        thread = corps.get("thread_id", "")
        res.append((bool(thread), "un thread_id est renvoye"))
        res.append(
            (
                corps.get("statut") == "en_attente_validation",
                f"la generation s'arrete pour validation (statut={corps.get('statut')})",
            ),
        )

        r = client.get(f"/pages/{thread}")
        res.append((r.status_code == 200, "GET /pages/{id} relit l'etat"))

        r = client.get("/pages/inconnu-42")
        res.append((r.status_code == 404, f"thread inconnu -> 404 (recu {r.status_code})"))

        r = client.post("/pages/inconnu-42/validation", json={"approuve": True})
        res.append((r.status_code == 404, "validation sur thread inconnu -> 404"))

        r = client.post(f"/pages/{thread}/validation", json={"approuve": True, "commentaire": ""})
        res.append((r.status_code == 200, f"validation approuvee -> 200 (recu {r.status_code})"))
        v = r.json()
        res.append((v.get("statut") == "publiee", f"statut publiee (recu {v.get('statut')})"))
        res.append(
            (bool(v.get("identifiant_publication")), "un identifiant de publication est renvoye")
        )

        r = client.post(f"/pages/{thread}/validation", json={"approuve": True})
        res.append((r.status_code == 409, f"rejouer la validation -> 409 (recu {r.status_code})"))

        r = client.post("/pages", json={"brief": ""})
        res.append(
            (r.status_code == 422, f"brief vide rejete a la frontiere (recu {r.status_code})")
        )

    reglages.cache_clear()
    return res


CH10 = Chapitre(
    numero=10,
    titre="L'API et la persistance",
    objectif="exposer la fabrique en HTTP et survivre a un redemarrage",
    duree_min=30,
    blocs=[
        T(
            "Un graphe qui tourne dans un notebook n'est pas un service. Ce chapitre "
            "pose la frontiere HTTP et la persistance, les deux choses qui separent une "
            "demo d'une application qu'on laisse tourner."
        ),
        H("La frontiere, et seulement la frontiere"),
        T(
            "La regle vaut pour tout le projet : validation stricte a la frontiere, "
            "confiance entre fonctions internes. Ici la frontiere est le corps de la "
            "requete. Un modele Pydantic par requete et par reponse, et FastAPI renvoie "
            "un 422 detaille sans que tu ecrives une ligne de controle."
        ),
        C("""class CreerPageRequete(BaseModel):
    brief: str = Field(min_length=1)
    pages_existantes: list[str] = Field(default_factory=list)

# brief vide -> 422 automatique, avec le champ fautif nomme"""),
        A(
            "Ne revalide pas ce corps plus loin dans la chaine. Une fois franchie la "
            "frontiere, les donnees sont dignes de confiance : c'est tout l'interet "
            "d'avoir une frontiere."
        ),
        H("Le thread_id est l'identite de la generation"),
        T(
            "Une generation qui attend une validation humaine peut attendre des heures. "
            "Ce qui la rend reprenable, c'est le couple checkpointer plus thread_id. Le "
            "thread_id voyage dans l'URL, le checkpointer garde l'etat. Sans les deux, "
            "l'interruption du chapitre 9 ne sert a rien."
        ),
        C("""config = {"configurable": {"thread_id": thread_id}}
# le thread_id passe dans configurable, pas a la racine de config"""),
        H("InMemorySaver ne survit pas au redemarrage"),
        T(
            "La doc le dit sans detour : InMemorySaver garde les checkpoints en RAM et "
            "tout est perdu au redemarrage du process. Pour la production elle "
            "recommande PostgresSaver. Le choix se fait au demarrage, selon la "
            "configuration."
        ),
        C("""from langgraph.checkpoint.postgres import PostgresSaver

checkpointer = PostgresSaver.from_conn_string(reglages().dsn)
checkpointer.setup()   # cree les tables et les index, une fois"""),
        A(
            "from_conn_string est un gestionnaire de contexte synchrone. Dans un "
            "lifespan asynchrone, il faut donc l'ouvrir dans un ExitStack et le garder "
            "vivant aussi longtemps que l'application. C'est le piege d'integration de "
            "ce chapitre."
        ),
        H("Le lifespan, pas on_event"),
        T(
            "Le checkpointer se cree une fois au demarrage et se ferme a l'arret. C'est "
            "le role du lifespan, un gestionnaire de contexte asynchrone passe a FastAPI. "
            "Les anciens decorateurs on_event sont deprecies."
        ),
        C("""@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    with ExitStack() as pile:
        app.state.checkpointer = ...
        yield

app = FastAPI(lifespan=lifespan)"""),
        H("Traduire les erreurs metier en codes HTTP"),
        T(
            "La taxonomie du chapitre 8 se transpose telle quelle. Budget depasse : 402, "
            "Payment Required, et c'est exactement ce que ca veut dire. Sortie invalide "
            "apres reparation : 422. Fournisseur fatal : 502. Surcharge : 503. Un "
            "gestionnaire d'exception par categorie, et les routes restent lisibles."
        ),
        C("""BudgetDepasse   -> 402    l'enveloppe de la page est epuisee
SortieInvalide  -> 422    le modele n'a pas produit de JSON conforme
Fatale          -> 502    cle invalide, modele inexistant, refus
Surcharge       -> 503    tous les fournisseurs sont satures"""),
        A(
            "Le 409 compte autant que les autres. Valider deux fois le meme thread doit "
            "echouer proprement, pas republier. C'est la meme idempotence que celle du "
            "chapitre 9, vue depuis la couche HTTP."
        ),
    ],
    questions=[
        Question(
            enonce="Pourquoi le thread_id doit-il etre stable entre deux appels HTTP ?",
            options=[
                "Pour les logs",
                "Parce que c'est lui qui retrouve l'etat sauvegarde et permet la reprise",
                "Pour l'authentification",
                "Il n'a pas besoin d'etre stable",
            ],
            bonne=1,
            explication="Le checkpointer indexe l'etat par thread_id. Sans lui, la "
            "generation interrompue est irrecuperable.",
            source="doc LangGraph persistence",
        ),
        Question(
            enonce="Tu redemarres le service avec InMemorySaver. Que deviennent les "
            "generations en attente de validation ?",
            options=[
                "Elles reprennent ou elles en etaient",
                "Elles sont perdues, la memoire ne survit pas au process",
                "Elles basculent automatiquement sur disque",
                "Elles sont rejouees depuis le debut",
            ],
            bonne=1,
            explication="La doc est explicite : InMemorySaver garde tout en RAM. En "
            "production, PostgresSaver.",
            source="doc LangGraph persistence",
        ),
        Question(
            enonce="Un client valide deux fois le meme thread. Reponse attendue ?",
            options=[
                "200, on republie",
                "409, le thread n'est plus en attente de validation",
                "500",
                "204",
            ],
            bonne=1,
            explication="Republier serait le bug du chapitre 9 vu depuis HTTP. Le 409 "
            "dit que l'etat ne permet pas l'operation.",
            source="auteur",
        ),
    ],
    kata=Kata(
        module="fabrique.api",
        consigne="Ecris les quatre routes de la fabrique. Le correcteur demarre "
        "reellement l'application avec TestClient, lance une generation, "
        "verifie qu'elle s'arrete pour validation, la reprend, et controle "
        "que rejouer la validation renvoie bien 409. Aucun serveur, aucune "
        "base, aucune cle.",
        squelette=SQ10,
        verifier=verif10,
        indice="TestClient(app) en gestionnaire de contexte declenche le lifespan. "
        "Un thread inconnu donne un instantane dont .values est vide, sans "
        "lever : c'est ton critere de 404. Pour le 409, fabrique.generation."
        "reprise.en_attente(graphe, config) repond deja a la question.",
        dependances=["fastapi", "langgraph"],
    ),
    a_retenir=[
        "Ou vit la validation et pourquoi elle n'est pas repetee plus loin.",
        "Ce qui se passe quand le service redemarre pendant qu'une page attend une "
        "validation humaine.",
        "Le code HTTP a renvoyer quand le budget d'une page est epuise, et pourquoi celui-la.",
    ],
    sources=[
        Source(
            "doc",
            "LangGraph persistence, checkpointers et thread_id",
            "https://docs.langchain.com/oss/python/langgraph/persistence",
        ),
        Source("execute", "fastapi 0.141.1, lifespan et TestClient declenchant le lifespan"),
        Source(
            "execute", "PostgresSaver.from_conn_string est un gestionnaire de contexte synchrone"
        ),
        Source("execute", "un thread inconnu renvoie un instantane vide, sans lever"),
        Source("auteur", "La correspondance entre la taxonomie d'erreurs et les codes HTTP"),
    ],
)
