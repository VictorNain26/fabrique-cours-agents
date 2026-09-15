"""Reglages lus depuis l'environnement. Frontiere : validation stricte ici."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Reglages(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    fournisseur: Literal["fake", "ovhcloud", "anthropic"] = "fake"
    budget_par_page: float = Field(default=0.50, gt=0)
    max_essais_reparation: int = Field(default=2, ge=1, le=5)
    max_tours_correction: int = Field(default=3, ge=1, le=10)

    ovh_api_key: str = ""
    ovh_base_url: str = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"
    ovh_modele: str = "Meta-Llama-3_3-70B-Instruct"

    anthropic_api_key: str = ""
    # Haiku par defaut : ce projet fait tourner des evaluations en boucle, et le
    # cout par page est une metrique du tableau de bord, pas un detail.
    anthropic_modele: str = "claude-haiku-4-5-20251001"

    database_url: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"


@lru_cache
def reglages() -> Reglages:
    return Reglages()
