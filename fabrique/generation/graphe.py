"""Graphe LangGraph de la fabrique : redaction, controle, correction,
tarification, validation humaine, publication.

Les dependances (validation, generation, repli, compaction, resolution des
prix) sont injectees a la racine, dans `construire`, pour que chaque etape se
teste avec des doubles.

La redaction passe par la chaine de repli : le premier fournisseur qui repond
gagne, et son nom remonte dans l'etat. Le budget est verifie avant chaque essai.
Les retours de correction s'accumulent dans l'etat et sont compactes sous un
budget de tokens avant chaque redaction.

La tarification resout le prix de chaque tableau_prix par le client MCP du
catalogue ; une reference inconnue renvoie en correction.

Un interrupt() est rejoue depuis le debut du noeud a chaque reprise : c'est
pourquoi l'effet de bord (publication) vit dans un noeud separe, execute
seulement apres l'approbation, jamais dans le noeud d'interruption.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy, interrupt

from fabrique.garde_fous import validateur
from fabrique.generation import contexte, reparation
from fabrique.mcp_catalogue import client as client_catalogue
from fabrique.mcp_catalogue.serveur import PrixResolu
from fabrique.modeles import EtatPage, Page, Violation
from fabrique.observabilite import observation, tracer_violation
from fabrique.providers import repli as repli_
from fabrique.providers.base import Fournisseur, Surcharge
from fabrique.providers.repli import Resultat

SYSTEME = "Tu generes une page web au format JSON strict conforme au schema fourni."


def _publier_neutre(page: Page) -> str:
    return "publication-neutre"


def _observe(nom: str, noeud: Callable[[EtatPage], dict]) -> Callable[[EtatPage], dict]:
    def enveloppe(etat: EtatPage) -> dict:
        fil = get_config()["configurable"]["thread_id"]
        with observation(nom, fil=fil, input=etat) as maj:
            sortie = noeud(etat)
            maj(output=sortie)
            return sortie

    return enveloppe


def construire(
    fournisseurs: list[Fournisseur],
    pages_existantes: set[str],
    *,
    checkpointer=None,
    max_tours: int = 3,
    budget_par_page: float = 0.50,
    budget_tokens_invite: int = 1500,
    publier: Callable[[Page], str] = _publier_neutre,
    valider: Callable[[Page, set[str]], list[Violation]] = validateur.valider,
    generer: Callable[..., Page] = reparation.generer_valide,
    repli: Callable[..., Resultat] = repli_.executer,
    compacter: Callable[
        [list[dict], int, Callable[[list[dict]], str]], list[dict]
    ] = contexte.compacter,
    resoudre_prix: Callable[[str], PrixResolu | None] = client_catalogue.resoudre_prix,
) -> CompiledStateGraph:
    def bornes(etat: EtatPage) -> bool:
        return etat.get("essais", 0) < max_tours

    def resumer(ecartes: list[dict]) -> str:
        codes = sorted(
            {
                ligne.split(":")[0].lstrip("- ")
                for message in ecartes
                for ligne in message["contenu"].splitlines()
                if ligne.startswith("- ")
            }
        )
        return "retours precedents resumes : " + ", ".join(codes)

    def invite_de(etat: EtatPage) -> str:
        messages = [
            {"role": "system", "contenu": etat["brief"], "tokens": contexte.estimer(etat["brief"])}
        ]
        messages += [
            {"role": "user", "contenu": retour, "tokens": contexte.estimer(retour)}
            for retour in etat.get("retours", [])
        ]
        gardes = compacter(messages, budget_tokens_invite, resumer)
        return "\n\n".join(message["contenu"] for message in gardes)

    def noeud_redaction(etat: EtatPage) -> dict:
        essais = etat.get("essais", 0) + 1
        invite = invite_de(etat)

        resultat = repli(
            fournisseurs,
            budget_par_page,
            lambda f: generer(f, invite=invite, schema=Page, systeme=SYSTEME),
        )

        return {
            "essais": essais,
            "page": resultat.valeur.model_dump(),
            "fournisseur": resultat.fournisseur,
            "cout": resultat.cout,
            "journal": [
                f"redaction: essai {essais}, {resultat.fournisseur}, {resultat.cout:.4f} EUR"
            ],
        }

    def noeud_controle(etat: EtatPage) -> dict:
        page = Page.model_validate(etat["page"])
        violations = valider(page, pages_existantes)

        for violation in violations:
            tracer_violation(violation)

        return {
            "violations": [v.model_dump() for v in violations],
            "journal": [
                f"controle: {len(violations)} violation(s), "
                f"{len(validateur.bloquantes(violations))} bloquante(s)"
            ],
        }

    def route_si_bloquant(suivant: str) -> Callable[[EtatPage], str]:
        def route(etat: EtatPage) -> str:
            violations = [Violation.model_validate(v) for v in etat.get("violations", [])]
            if validateur.bloquantes(violations) and bornes(etat):
                return "correction"
            return suivant

        return route

    def noeud_correction(etat: EtatPage) -> dict:
        violations = [Violation.model_validate(v) for v in etat.get("violations", [])]
        lignes = [
            f"- {v.code}: {v.message} {v.indice}".rstrip()
            for v in validateur.bloquantes(violations)
        ]
        return {
            "retours": ["retour_correction:\n" + "\n".join(lignes)],
            "journal": [f"correction: {len(lignes)} retour(s)"],
        }

    def noeud_tarification(etat: EtatPage) -> dict:
        page = Page.model_validate(etat["page"])
        inconnues: list[str] = []
        blocs = []
        for bloc in page.blocs:
            prix = None
            if bloc.type == "tableau_prix" and bloc.product_ref:
                resolu = resoudre_prix(bloc.product_ref)
                if resolu is None:
                    inconnues.append(bloc.product_ref)
                else:
                    prix = resolu.libelle_affichable
            blocs.append(bloc.model_copy(update={"prix_affiche": prix}))

        violations = [
            Violation(
                code="REF_PRODUIT_INCONNUE",
                gravite="bloquant",
                message=f"La reference '{reference}' n'existe pas au catalogue.",
                indice="Utilise une reference du catalogue (chercher_produit).",
            )
            for reference in inconnues
        ]
        return {
            "page": page.model_copy(update={"blocs": blocs}).model_dump(),
            # Quand les tours sont epuises, le controle route ici malgre ses
            # violations bloquantes : les ecraser les cacherait au relecteur.
            "violations": etat.get("violations", []) + [v.model_dump() for v in violations],
            "journal": [
                f"tarification: {len(blocs)} bloc(s), {len(inconnues)} reference(s) inconnue(s)"
            ],
        }

    def noeud_validation_humaine(etat: EtatPage) -> dict:
        reponse = interrupt({"page": etat.get("page"), "violations": etat.get("violations", [])})
        return {
            "approuve": bool(reponse.get("approuve", False)),
            "commentaire_humain": reponse.get("commentaire", ""),
        }

    def route_apres_validation(etat: EtatPage) -> Literal["publication", "__end__"]:
        return "publication" if etat.get("approuve") else END

    def noeud_publication(etat: EtatPage) -> dict:
        page = Page.model_validate(etat["page"])
        identifiant = publier(page)
        return {"publiee": True, "journal": [f"publication: {identifiant}"]}

    graphe = StateGraph(EtatPage)
    graphe.add_node(
        "redaction",
        _observe("redaction", noeud_redaction),
        # executer() possede deja la politique par categorie : bascule sur
        # Surcharge, un re-essai sur SortieInvalide, propagation sur Fatale. Ce
        # retry-ci ne couvre que le cas ou TOUTE la chaine etait saturee.
        retry_policy=RetryPolicy(max_attempts=2, retry_on=(Surcharge,)),
    )
    graphe.add_node("controle", _observe("controle", noeud_controle))
    graphe.add_node("correction", _observe("correction", noeud_correction))
    graphe.add_node("tarification", _observe("tarification", noeud_tarification))
    graphe.add_node("validation_humaine", noeud_validation_humaine)
    graphe.add_node("publication", _observe("publication", noeud_publication))

    graphe.add_edge(START, "redaction")
    graphe.add_edge("redaction", "controle")
    graphe.add_conditional_edges(
        "controle", route_si_bloquant("tarification"), ["correction", "tarification"]
    )
    graphe.add_conditional_edges(
        "tarification",
        route_si_bloquant("validation_humaine"),
        ["correction", "validation_humaine"],
    )
    graphe.add_edge("correction", "redaction")
    graphe.add_conditional_edges("validation_humaine", route_apres_validation)
    graphe.add_edge("publication", END)

    return graphe.compile(checkpointer=checkpointer)
