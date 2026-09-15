"""Golden dataset de briefs pour l'evaluation de la fabrique de pages.

Verse dans le depot, versionne avec le code : chaque cas doit rester
reproductible sans reseau ni cle Langfuse.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CasGolden(BaseModel):
    identifiant: str
    brief: str
    pages_existantes: set[str] = Field(default_factory=set)
    attendus: dict[str, Any] = Field(default_factory=dict)


CAS: list[CasGolden] = [
    CasGolden(
        identifiant="hebergement-mutualise",
        brief=(
            "Cree une page de vente pour notre offre d'hebergement web mutualise, "
            "destinee aux createurs de petits sites vitrine."
        ),
        pages_existantes={"/accueil", "/hebergement"},
        attendus={
            "nb_h1": 1,
            "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE", "REF_PRODUIT_MANQUANTE"],
            "refs_produit_attendues": ["hebergement-mutualise"],
        },
    ),
    CasGolden(
        identifiant="nom-de-domaine",
        brief="Cree une page qui presente notre service d'enregistrement de noms de domaine.",
        pages_existantes={"/accueil", "/domaines"},
        attendus={"nb_h1": 1, "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE"]},
    ),
    CasGolden(
        identifiant="vps-cloud",
        brief="Redige une page comparant nos trois offres de VPS cloud (petit, moyen, grand).",
        pages_existantes={"/accueil", "/vps"},
        attendus={
            "nb_h1": 1,
            "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE", "REF_PRODUIT_MANQUANTE"],
            "refs_produit_attendues": ["vps-petit", "vps-moyen", "vps-grand"],
        },
    ),
    CasGolden(
        identifiant="certificat-ssl",
        brief="Cree une page qui explique les certificats SSL disponibles et pourquoi les activer.",
        pages_existantes={"/accueil", "/ssl"},
        attendus={"nb_h1": 1, "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE"]},
    ),
    CasGolden(
        identifiant="page-a-propos",
        brief="Redige une page 'A propos' presentant l'histoire de l'entreprise, sans offre commerciale.",
        pages_existantes={"/accueil"},
        attendus={
            "nb_h1": 1,
            "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE", "REF_PRODUIT_MANQUANTE"],
        },
    ),
    CasGolden(
        identifiant="comparatif-offres",
        brief="Cree une page comparatif qui met cote a cote toutes nos offres d'hebergement avec leurs tableaux de prix.",
        pages_existantes={"/accueil", "/hebergement", "/vps"},
        attendus={
            "nb_h1": 1,
            "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE", "REF_PRODUIT_MANQUANTE"],
            "refs_produit_attendues": ["hebergement-mutualise", "vps-petit"],
        },
    ),
    CasGolden(
        identifiant="faq-support",
        brief="Redige une page FAQ sur le support technique, avec des liens vers les pages d'offres existantes.",
        pages_existantes={"/accueil", "/hebergement", "/vps", "/ssl"},
        attendus={"nb_h1": 1, "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE"]},
    ),
    CasGolden(
        identifiant="migration-cloud",
        brief="Cree une page qui accompagne un client dans sa migration d'un serveur dedie vers le cloud.",
        pages_existantes={"/accueil", "/vps"},
        attendus={"nb_h1": 1, "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE"]},
    ),
    CasGolden(
        identifiant="programme-partenaires",
        brief="Redige une page destinee aux revendeurs qui souhaitent rejoindre notre programme partenaires.",
        pages_existantes={"/accueil"},
        attendus={"nb_h1": 1, "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE"]},
    ),
    CasGolden(
        identifiant="stockage-objet",
        brief="Cree une page vendant notre service de stockage objet compatible S3.",
        pages_existantes={"/accueil"},
        attendus={
            "nb_h1": 1,
            "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE", "REF_PRODUIT_MANQUANTE"],
            "refs_produit_attendues": ["stockage-objet"],
        },
    ),
    CasGolden(
        identifiant="meta-description-borne-basse",
        brief=(
            "Redige une page tres courte sur notre offre email professionnel, "
            "avec une meta description tenant tout juste dans la limite basse autorisee."
        ),
        pages_existantes={"/accueil"},
        attendus={
            "nb_h1": 1,
            "meta_description_bornes": [120, 158],
            "codes_interdits": ["PRIX_EN_DUR"],
        },
    ),
    CasGolden(
        identifiant="meta-description-borne-haute",
        brief=(
            "Redige une page detaillee sur notre offre de sauvegarde automatisee, "
            "avec une meta description qui utilise presque toute la limite haute autorisee."
        ),
        pages_existantes={"/accueil"},
        attendus={
            "nb_h1": 1,
            "meta_description_bornes": [120, 158],
            "codes_interdits": ["PRIX_EN_DUR"],
        },
    ),
    CasGolden(
        identifiant="brief-vide",
        brief="",
        pages_existantes={"/accueil"},
        attendus={"codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE"]},
    ),
    CasGolden(
        identifiant="brief-demande-prix-en-dur",
        brief="Cree une page pour le VPS moyen et indique bien le prix de 19,99€ par mois directement dans le texte.",
        pages_existantes={"/accueil", "/vps"},
        attendus={
            "nb_h1": 1,
            "codes_interdits": ["PRIX_EN_DUR"],
            "refs_produit_attendues": ["vps-moyen"],
        },
    ),
    CasGolden(
        identifiant="cible-invente-type-bloc",
        brief="Cree une page produit avec une video de presentation integree en tete de page.",
        pages_existantes={"/accueil"},
        attendus={"nb_h1": 1, "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE"]},
    ),
    CasGolden(
        identifiant="regression-deux-h1",
        brief="Cree une page avec un grand titre principal et un sous-titre tout aussi visible en haut de page.",
        pages_existantes={"/accueil"},
        attendus={"nb_h1": 1, "codes_interdits": ["H1_MULTIPLE"]},
    ),
    CasGolden(
        identifiant="regression-ref-produit-manquante",
        brief="Cree une page presentant le tarif de notre offre hebergement dans un tableau de prix.",
        pages_existantes={"/accueil", "/hebergement"},
        attendus={
            "nb_h1": 1,
            "codes_interdits": ["REF_PRODUIT_MANQUANTE", "PRIX_EN_DUR"],
            "refs_produit_attendues": ["hebergement-mutualise"],
        },
    ),
    CasGolden(
        identifiant="lien-vers-page-inexistante",
        brief="Cree une page d'offres qui renvoie vers une page de temoignages clients pas encore publiee.",
        pages_existantes={"/accueil"},
        attendus={"nb_h1": 1, "codes_interdits": ["PRIX_EN_DUR", "H1_MULTIPLE"]},
    ),
]
