"""Garde-fous deterministes appliques a une Page avant publication.

Aucun appel LLM ici : chaque regle est une fonction pure sur les donnees deja
validees par les modeles Pydantic de `fabrique.modeles`.
"""

from __future__ import annotations

import re

from fabrique.modeles import Page, Violation

MOTIF_PRIX = re.compile(r"\d+(?:[.,]\d+)?\s*(?:€|eur\b|euros?\b)", re.IGNORECASE)


def valider(page: Page, pages_existantes: set[str]) -> list[Violation]:
    violations: list[Violation] = []

    nb_titres = sum(1 for bloc in page.blocs if bloc.type == "titre")
    if nb_titres != 1:
        violations.append(
            Violation(
                code="H1_MULTIPLE",
                gravite="bloquant",
                message=f"La page contient {nb_titres} bloc(s) de type 'titre' au lieu d'un seul.",
                indice="Garde exactement un bloc de type titre dans la page.",
            )
        )

    for bloc in page.blocs:
        if MOTIF_PRIX.search(bloc.contenu):
            violations.append(
                Violation(
                    code="PRIX_EN_DUR",
                    gravite="bloquant",
                    message=f"Le bloc '{bloc.contenu}' contient un prix en dur.",
                    indice="Emets un bloc tableau_prix avec product_ref, le prix est resolu par le catalogue.",
                )
            )

        if bloc.type == "tableau_prix" and bloc.product_ref is None:
            violations.append(
                Violation(
                    code="REF_PRODUIT_MANQUANTE",
                    gravite="bloquant",
                    message="Un bloc tableau_prix n'a pas de product_ref.",
                    indice="Renseigne product_ref sur le bloc tableau_prix avec la reference du catalogue.",
                )
            )

    for lien in page.liens:
        if lien not in pages_existantes:
            violations.append(
                Violation(
                    code="LIEN_MORT",
                    gravite="avertissement",
                    message=f"Le lien '{lien}' ne pointe vers aucune page existante.",
                    indice=f"Retire le lien '{lien}' ou cree la page correspondante avant de le referencer.",
                )
            )

    return violations


def bloquantes(violations: list[Violation]) -> list[Violation]:
    return [violation for violation in violations if violation.gravite == "bloquant"]
