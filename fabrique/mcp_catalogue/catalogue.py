"""Source de verite des produits. Aucun prix ne doit etre invente ailleurs."""

from __future__ import annotations

from pydantic import BaseModel


class Produit(BaseModel):
    reference: str
    nom: str
    vcores: int
    ram_go: int
    prix_mensuel_eur: float
    gamme: str


_CATALOGUE: dict[str, Produit] = {
    "vps-starter": Produit(
        reference="vps-starter",
        nom="VPS Starter",
        vcores=1,
        ram_go=2,
        prix_mensuel_eur=3.99,
        gamme="entree",
    ),
    "vps-comfort": Produit(
        reference="vps-comfort",
        nom="VPS Comfort",
        vcores=2,
        ram_go=4,
        prix_mensuel_eur=7.99,
        gamme="milieu",
    ),
    "vps-elite": Produit(
        reference="vps-elite",
        nom="VPS Elite",
        vcores=4,
        ram_go=8,
        prix_mensuel_eur=15.99,
        gamme="haut",
    ),
    "vps-pro": Produit(
        reference="vps-pro",
        nom="VPS Pro",
        vcores=8,
        ram_go=16,
        prix_mensuel_eur=31.99,
        gamme="haut",
    ),
    "stockage-standard": Produit(
        reference="stockage-standard",
        nom="Stockage Standard",
        vcores=0,
        ram_go=0,
        prix_mensuel_eur=1.5,
        gamme="entree",
    ),
    "stockage-performance": Produit(
        reference="stockage-performance",
        nom="Stockage Performance",
        vcores=0,
        ram_go=0,
        prix_mensuel_eur=4.5,
        gamme="milieu",
    ),
}


def get(reference: str) -> Produit | None:
    return _CATALOGUE.get(reference)


def chercher(requete: str) -> list[Produit]:
    termes = requete.lower().split()
    if not termes:
        return list(_CATALOGUE.values())
    return [
        produit
        for produit in _CATALOGUE.values()
        if all(
            terme in produit.nom.lower()
            or terme in produit.reference.lower()
            or terme in produit.gamme.lower()
            for terme in termes
        )
    ]
