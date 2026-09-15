"""Serveur MCP exposant le catalogue produits.

Un tableau de prix genere par le modele ne porte jamais de prix en dur : il
designe un produit par sa reference, et c'est ce serveur qui resout le prix
reel a partir du catalogue.
"""

from __future__ import annotations

from mcp.server import MCPServer
from pydantic import BaseModel

from fabrique.mcp_catalogue import catalogue
from fabrique.mcp_catalogue.catalogue import Produit


class PrixResolu(BaseModel):
    reference: str
    prix_mensuel_eur: float
    libelle_affichable: str


def construire() -> MCPServer:
    serveur = MCPServer("catalogue-hebergeur")

    @serveur.tool()
    def chercher_produit(requete_en_langage_naturel: str) -> list[Produit]:
        """Recherche des produits du catalogue par mots-cles (nom, gamme,
        reference). A utiliser pour decouvrir quel produit correspond a un
        besoin exprime en langage naturel, par exemple "un serveur pas cher
        pour debuter" ou "du stockage performant". Ne pas utiliser cet outil
        si la reference exacte du produit est deja connue : appeler plutot
        get_produit ou resoudre_prix directement avec cette reference.
        """
        return catalogue.chercher(requete_en_langage_naturel)

    @serveur.tool()
    def get_produit(reference: str) -> Produit | None:
        """Recupere la fiche complete d'un produit (nom, vcores, ram, gamme,
        prix) a partir de sa reference exacte dans le catalogue, ou None si
        cette reference n'existe pas. Ne pas utiliser cet outil pour trouver
        une reference a partir d'une simple description : dans ce cas,
        appeler d'abord chercher_produit.
        """
        return catalogue.get(reference)

    @serveur.tool()
    def resoudre_prix(reference: str) -> PrixResolu:
        """Resout le prix mensuel reel d'un produit a partir de sa reference,
        pour remplacer tout prix qu'un tableau_prix ne doit jamais afficher
        en dur. A utiliser systematiquement avant de publier un bloc
        tableau_prix. Ne pas utiliser cet outil avec une reference inventee
        ou non confirmee par chercher_produit ou get_produit au prealable.
        """
        produit = catalogue.get(reference)
        if produit is None:
            raise ValueError(f"reference inconnue au catalogue: {reference}")
        return PrixResolu(
            reference=produit.reference,
            prix_mensuel_eur=produit.prix_mensuel_eur,
            libelle_affichable=f"{produit.prix_mensuel_eur:.2f} EUR / mois",
        )

    return serveur
