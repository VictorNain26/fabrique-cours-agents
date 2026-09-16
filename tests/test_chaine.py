from __future__ import annotations

import pytest
from pydantic import ValidationError

from fabrique.config import Reglages
from fabrique.providers.anthropic import FournisseurAnthropic
from fabrique.providers.chaine import chaine_depuis_reglages
from fabrique.providers.fake import FournisseurFake
from fabrique.providers.ovhcloud import FournisseurOVHcloud


def test_la_chaine_suit_l_ordre_declare_et_porte_l_enveloppe() -> None:
    parametres = Reglages(
        fournisseurs="ovhcloud,anthropic,fake",
        ovh_api_key="k",
        anthropic_api_key="k",
        cout_estime_ovhcloud=0.002,
        cout_estime_anthropic=0.01,
    )

    chaine = chaine_depuis_reglages(parametres)

    assert [type(f) for f in chaine] == [FournisseurOVHcloud, FournisseurAnthropic, FournisseurFake]
    assert [f.cout_par_appel for f in chaine] == [0.002, 0.01, 0.0]
    assert chaine[1].modele == parametres.anthropic_modele


def test_un_nom_inconnu_est_refuse_a_la_frontiere() -> None:
    with pytest.raises(ValidationError, match="ovhclou"):
        Reglages(fournisseurs="ovhclou")


def test_le_budget_par_defaut_couvre_plusieurs_essais() -> None:
    parametres = Reglages(_env_file=None)
    assert parametres.budget_par_page > 10 * max(
        parametres.cout_estime_ovhcloud, parametres.cout_estime_anthropic
    )


def test_anthropic_exige_un_modele() -> None:
    with pytest.raises(TypeError):
        FournisseurAnthropic(api_key="k")
