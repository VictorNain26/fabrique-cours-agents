"""Construit la chaine de repli declaree dans les reglages."""

from __future__ import annotations

from fabrique.config import Reglages
from fabrique.providers.anthropic import FournisseurAnthropic
from fabrique.providers.base import Fournisseur
from fabrique.providers.fake import FournisseurFake
from fabrique.providers.ovhcloud import FournisseurOVHcloud


def _un_fournisseur(nom: str, parametres: Reglages) -> Fournisseur:
    if nom == "ovhcloud":
        return FournisseurOVHcloud(
            api_key=parametres.ovh_api_key,
            base_url=parametres.ovh_base_url,
            modele=parametres.ovh_modele,
            cout_par_appel=parametres.cout_estime_ovhcloud,
        )
    if nom == "anthropic":
        return FournisseurAnthropic(
            api_key=parametres.anthropic_api_key,
            modele=parametres.anthropic_modele,
            cout_par_appel=parametres.cout_estime_anthropic,
        )
    return FournisseurFake()


def chaine_depuis_reglages(parametres: Reglages) -> list[Fournisseur]:
    return [_un_fournisseur(nom, parametres) for nom in parametres.chaine]
