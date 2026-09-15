"""Graphe LangGraph de la fabrique : redaction, controle, correction, validation
humaine, publication.

La redaction passe par la chaine de repli : le premier fournisseur qui repond
gagne, et son nom remonte dans l'etat. Le budget est verifie avant chaque essai.

Un interrupt() est rejoue depuis le debut du noeud a chaque reprise : c'est
pourquoi l'effet de bord (publication) vit dans un noeud separe, execute
seulement apres l'approbation, jamais dans le noeud d'interruption.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Overwrite, RetryPolicy, interrupt

from fabrique.garde_fous.validateur import bloquantes, valider
from fabrique.generation.reparation import generer_valide
from fabrique.modeles import EtatPage, Page, Violation
from fabrique.providers.base import Fournisseur, Surcharge
from fabrique.providers.repli import executer

SYSTEME = "Tu generes une page web au format JSON strict conforme au schema fourni."


def _publier_neutre(page: Page) -> str:
    return "publication-neutre"


def _dernier_retour(journal: list[str]) -> str | None:
    for entree in reversed(journal):
        if entree.startswith("retour_correction:"):
            return entree
    return None


def construire(
    fournisseurs: list[Fournisseur],
    pages_existantes: set[str],
    *,
    checkpointer=None,
    max_tours: int = 3,
    budget_par_page: float = 0.50,
    publier: Callable[[Page], str] = _publier_neutre,
) -> CompiledStateGraph:
    def bornes(etat: EtatPage) -> bool:
        return etat.get("essais", 0) < max_tours

    def noeud_redaction(etat: EtatPage) -> dict:
        essais = etat.get("essais", 0) + 1
        retour = _dernier_retour(etat.get("journal", []))
        invite = etat["brief"] if retour is None else f"{etat['brief']}\n\n{retour}"

        resultat = executer(
            fournisseurs,
            budget_par_page,
            lambda f: generer_valide(f, invite=invite, schema=Page, systeme=SYSTEME),
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

        return {
            "violations": [v.model_dump() for v in violations],
            "journal": [
                f"controle: {len(violations)} violation(s), "
                f"{len(bloquantes(violations))} bloquante(s)"
            ],
        }

    def route_apres_controle(etat: EtatPage) -> Literal["correction", "validation_humaine"]:
        violations = [Violation.model_validate(v) for v in etat.get("violations", [])]
        if bloquantes(violations) and bornes(etat):
            return "correction"
        return "validation_humaine"

    def noeud_correction(etat: EtatPage) -> dict:
        violations = [Violation.model_validate(v) for v in etat.get("violations", [])]
        lignes = [f"- {v.code}: {v.message} {v.indice}".rstrip() for v in bloquantes(violations)]
        retour = "retour_correction:\n" + "\n".join(lignes)

        # WHY : le journal fusionne par defaut (reducteur qui concatene). On le
        # vide ici volontairement pour que "redaction" ne relise que le retour
        # du tour courant, pas l'historique cumule des tours precedents.
        return {"journal": Overwrite(value=[retour])}

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
        noeud_redaction,
        # executer() possede deja la politique par categorie : bascule sur
        # Surcharge, un re-essai sur SortieInvalide, propagation sur Fatale. Ce
        # retry-ci ne couvre que le cas ou TOUTE la chaine etait saturee.
        retry_policy=RetryPolicy(max_attempts=2, retry_on=(Surcharge,)),
    )
    graphe.add_node("controle", noeud_controle)
    graphe.add_node("correction", noeud_correction)
    graphe.add_node("validation_humaine", noeud_validation_humaine)
    graphe.add_node("publication", noeud_publication)

    graphe.add_edge(START, "redaction")
    graphe.add_edge("redaction", "controle")
    graphe.add_conditional_edges("controle", route_apres_controle)
    graphe.add_edge("correction", "redaction")
    graphe.add_conditional_edges("validation_humaine", route_apres_validation)
    graphe.add_edge("publication", END)

    return graphe.compile(checkpointer=checkpointer)
