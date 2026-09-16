"""Fournisseur OVHcloud AI Endpoints, via le client `openai` (API compatible OpenAI).

La sortie structuree d'OVHcloud AI Endpoints ne supporte qu'un sous-ensemble du
JSON Schema : « Structured output currently supports a subset of the JSON
schema specification. Some features may not be compatible. »
Source : https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-structured-output
"""

from __future__ import annotations

import openai
from pydantic import BaseModel

from fabrique.observabilite import observation

from .base import Fatale, Reponse, SortieInvalide, Surcharge

BASE_URL_OVHCLOUD = "https://oai.endpoints.kepler.ai.cloud.ovh.net/v1"
MODELE_OVHCLOUD = "Meta-Llama-3_3-70B-Instruct"

# Tarif du README (« Ce que ça coûte »), entree comme sortie. Il est en euros et
# `cost_details` attend des dollars : le cout part en metadonnee plutot que de
# passer par un taux de change invente.
TARIFS_EUR_PAR_MILLION = {MODELE_OVHCLOUD: 0.67}


class FournisseurOVHcloud:
    nom = "ovhcloud"

    def __init__(
        self,
        api_key: str,
        base_url: str = BASE_URL_OVHCLOUD,
        modele: str = MODELE_OVHCLOUD,
        cout_par_appel: float = 0.0,
    ) -> None:
        self.modele = modele
        self.cout_par_appel = cout_par_appel
        self._client = openai.OpenAI(api_key=api_key, base_url=base_url)

    def generer(
        self,
        *,
        invite: str,
        schema: type[BaseModel],
        systeme: str = "",
        retour: str | None = None,
    ) -> Reponse:
        messages: list[dict[str, str]] = []
        if systeme:
            messages.append({"role": "system", "content": systeme})
        messages.append({"role": "user", "content": invite})
        if retour is not None:
            messages.append({"role": "user", "content": f"L'essai precedent a echoue : {retour}"})

        with observation(
            self.nom,
            as_type="generation",
            model=self.modele,
            model_parameters={"temperature": 0},
            input=messages,
        ) as maj:
            try:
                # La doc OVHcloud montre encore la forme beta
                # (`openai_client.beta.chat.completions.parse`) ; en openai 3.14.0,
                # `chat.completions.parse` existe hors beta, on utilise la forme stable.
                completion = self._client.chat.completions.parse(
                    model=self.modele,
                    messages=messages,
                    response_format=schema,
                    temperature=0,
                )
            except openai.RateLimitError as erreur:
                raise Surcharge(str(erreur)) from erreur
            except (openai.APIConnectionError, openai.APITimeoutError) as erreur:
                raise Surcharge(str(erreur)) from erreur
            except (
                openai.AuthenticationError,
                openai.PermissionDeniedError,
                openai.NotFoundError,
            ) as erreur:
                raise Fatale(str(erreur)) from erreur
            except (
                openai.LengthFinishReasonError,
                openai.ContentFilterFinishReasonError,
            ) as erreur:
                raise SortieInvalide(str(erreur)) from erreur

            usage = completion.usage
            tokens_entree = usage.prompt_tokens if usage else 0
            tokens_sortie = usage.completion_tokens if usage else 0
            tarif = TARIFS_EUR_PAR_MILLION.get(self.modele)
            maj(
                model=completion.model,
                usage_details={"input": tokens_entree, "output": tokens_sortie},
                metadata=None
                if tarif is None
                else {"cout_eur": (tokens_entree + tokens_sortie) * tarif / 1_000_000},
            )

            message = completion.choices[0].message
            if message.refusal:
                raise SortieInvalide(message.refusal)
            if message.parsed is None:
                raise SortieInvalide("reponse non conforme au schema")

            texte = message.parsed.model_dump_json()
            maj(output=texte)
            return Reponse(
                texte=texte,
                modele=completion.model,
                tokens_entree=tokens_entree,
                tokens_sortie=tokens_sortie,
            )
