"""Evaluateurs purs sur une sortie de la fabrique.

Aucun reseau, aucune dependance a Langfuse pour le calcul : chaque fonction
accepte soit une `Page` deja validee, soit un dict de meme forme (par exemple
`Page.model_dump()` avant repassage dans le schema strict), et rend un verdict
0/1 exploitable en CI comme en experience Langfuse.
"""

from __future__ import annotations

from typing import Any

from langfuse import Evaluation

from fabrique.garde_fous.validateur import bloquantes, valider
from fabrique.mcp_catalogue import catalogue
from fabrique.modeles import BlocPage, Page


def _bloc_comme_bloc_page(bloc: Any) -> BlocPage:
    if isinstance(bloc, BlocPage):
        return bloc
    return BlocPage.model_construct(**bloc)


def _sortie_comme_page(output: Any) -> Page:
    if isinstance(output, Page):
        return output

    return Page.model_construct(
        titre_h1=output.get("titre_h1", ""),
        meta_description=output.get("meta_description", ""),
        blocs=[_bloc_comme_bloc_page(bloc) for bloc in output.get("blocs", [])],
        liens=output.get("liens", []),
    )


def sans_violation_bloquante(
    *,
    input: Any,
    output: Any,
    expected_output: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Evaluation:
    page = _sortie_comme_page(output)
    pages_existantes = set((metadata or {}).get("pages_existantes", []))
    violations = valider(page, pages_existantes)

    codes_interdits = set((expected_output or {}).get("codes_interdits", []))
    codes_presents = {v.code for v in violations}
    en_echec = bool(bloquantes(violations)) or bool(codes_interdits & codes_presents)

    return Evaluation(
        name="sans_violation_bloquante",
        value=0.0 if en_echec else 1.0,
        comment="aucune violation"
        if not en_echec
        else f"violations presentes: {sorted(codes_presents)}",
    )


def respecte_longueurs(
    *,
    input: Any,
    output: Any,
    expected_output: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Evaluation:
    page = _sortie_comme_page(output)
    longueur_meta = len(page.meta_description)
    longueur_titre = len(page.titre_h1)
    ok = 120 <= longueur_meta <= 158 and longueur_titre <= 70

    return Evaluation(
        name="respecte_longueurs",
        value=1.0 if ok else 0.0,
        comment=f"meta_description={longueur_meta} caracteres, titre_h1={longueur_titre} caracteres",
    )


def refs_produit_resolues(
    *,
    input: Any,
    output: Any,
    expected_output: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    **kwargs: Any,
) -> Evaluation:
    page = _sortie_comme_page(output)
    fautifs = [
        bloc.contenu
        for bloc in page.blocs
        if bloc.type == "tableau_prix" and not _prix_du_catalogue(bloc)
    ]

    return Evaluation(
        name="refs_produit_resolues",
        value=1.0 if not fautifs else 0.0,
        comment="toutes les refs produit sont resolues"
        if not fautifs
        else f"blocs sans prix resolu depuis le catalogue: {fautifs}",
    )


def _prix_du_catalogue(bloc: BlocPage) -> bool:
    produit = catalogue.get(bloc.product_ref) if bloc.product_ref else None
    if produit is None:
        return False
    return bloc.prix_affiche == f"{produit.prix_mensuel_eur:.2f} EUR / mois"
