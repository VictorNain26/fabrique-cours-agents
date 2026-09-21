"""Reglages lus depuis l'environnement. Frontiere : validation stricte ici."""

from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

FOURNISSEURS_CONNUS = {"fake", "ovhcloud", "anthropic"}


class Reglages(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Chaine de repli, du moins cher au plus cher. "fake" seul en defaut :
    # ni les tests ni la CI ne doivent depenser d'argent.
    fournisseurs: str = "fake"
    budget_par_page: float = Field(default=0.50, gt=0)
    max_essais_reparation: int = Field(default=2, ge=1, le=5)
    max_tours_correction: int = Field(default=3, ge=1, le=10)

    # Enveloppe debitee AVANT chaque essai, en euros. Estimee pour une page
    # (~1500 tokens en entree, ~800 en sortie) : OVHcloud 0,67 EUR/M tokens,
    # Haiku 4.5 1 $/M en entree et 5 $/M en sortie, arrondi au-dessus.
    cout_estime_ovhcloud: float = Field(default=0.002, ge=0)
    cout_estime_anthropic: float = Field(default=0.01, ge=0)
    budget_tokens_invite: int = Field(default=1500, ge=100)

    @field_validator("fournisseurs")
    @classmethod
    def _noms_connus(cls, valeur: str) -> str:
        noms = {n.strip() for n in valeur.split(",") if n.strip()}
        if not noms:
            raise ValueError("aucun fournisseur dans FOURNISSEURS (ex. : fake)")
        inconnus = noms - FOURNISSEURS_CONNUS
        if inconnus:
            raise ValueError(f"fournisseurs inconnus : {sorted(inconnus)}")
        return valeur

    temporal_host: str = ""
    temporal_namespace: str = "default"
    temporal_task_queue: str = "fabrique"

    ovh_api_key: str = ""
    ovh_base_url: str = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"
    ovh_modele: str = "Meta-Llama-3_3-70B-Instruct"

    anthropic_api_key: str = ""
    # Haiku par defaut : ce projet fait tourner des evaluations en boucle, et le
    # cout par page est une metrique du tableau de bord, pas un detail.
    anthropic_modele: str = "claude-haiku-4-5-20251001"

    # Les composants plutot qu'un DSN assemble : aucune URL porteuse d'identifiants
    # ne figure dans le depot, et le secret reste une variable isolee.
    postgres_host: str = ""
    postgres_port: int = 5432
    postgres_user: str = "fabrique"
    postgres_password: str = ""
    postgres_db: str = "fabrique"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    @property
    def dsn(self) -> str:
        """Chaine de connexion Postgres, ou "" si aucune base n'est configuree."""
        if not self.postgres_host:
            return ""
        mot_de_passe = quote(self.postgres_password, safe="")
        return (
            f"postgresql://{quote(self.postgres_user, safe='')}:{mot_de_passe}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def chaine(self) -> list[str]:
        return [n.strip() for n in self.fournisseurs.split(",") if n.strip()]


@lru_cache
def reglages() -> Reglages:
    return Reglages()
