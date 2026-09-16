"""Fournisseur Anthropic (Claude), sortie structuree via tool-use.

`anthropic` est epingle dans requirements.txt, mais l'import reste fait dans le
constructeur : l'API importe ce module au demarrage meme quand la chaine ne
compte que le fournisseur factice, et les tests substituent un faux module
`anthropic` au moment de la construction.

Technique de sortie structuree documentee par Anthropic : declarer un outil
unique dont le `input_schema` est le JSON Schema du modele Pydantic vise, puis
forcer son usage avec `tool_choice={"type": "tool", "name": ...}`.
Source : https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
(section « Forcing tool use »).

Taxonomie des erreurs verifiee dans
https://github.com/anthropics/anthropic-sdk-python/blob/main/src/anthropic/_exceptions.py
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ValidationError

from .base import Fatale, Reponse, SortieInvalide, Surcharge

NOM_OUTIL = "produire_sortie"
MAX_TOKENS = 4096


class FournisseurAnthropic:
    nom = "anthropic"

    def __init__(
        self,
        api_key: str,
        modele: str = "claude-sonnet-5",
        cout_par_appel: float = 0.0,
    ) -> None:
        try:
            import anthropic
        except ImportError as erreur:
            raise ImportError(
                "le paquet 'anthropic' est requis pour FournisseurAnthropic (pip install anthropic)"
            ) from erreur

        self._anthropic = anthropic
        self.modele = modele
        self.cout_par_appel = cout_par_appel
        self._client = anthropic.Anthropic(api_key=api_key)

    def generer(
        self,
        *,
        invite: str,
        schema: type[BaseModel],
        systeme: str = "",
        retour: str | None = None,
    ) -> Reponse:
        anthropic = self._anthropic
        messages: list[dict[str, Any]] = [{"role": "user", "content": invite}]
        if retour is not None:
            messages.append({"role": "user", "content": f"L'essai precedent a echoue : {retour}"})

        outil = {
            "name": NOM_OUTIL,
            "description": f"Produit une sortie conforme au schema {schema.__name__}.",
            "input_schema": schema.model_json_schema(),
        }

        arguments: dict[str, Any] = {
            "model": self.modele,
            "max_tokens": MAX_TOKENS,
            "messages": messages,
            "tools": [outil],
            "tool_choice": {"type": "tool", "name": NOM_OUTIL},
        }
        if systeme:
            arguments["system"] = systeme

        try:
            message = self._client.messages.create(**arguments)
        except anthropic.RateLimitError as erreur:
            raise Surcharge(str(erreur)) from erreur
        except anthropic.OverloadedError as erreur:
            raise Surcharge(str(erreur)) from erreur
        except (anthropic.APIConnectionError, anthropic.APITimeoutError) as erreur:
            raise Surcharge(str(erreur)) from erreur
        except (
            anthropic.AuthenticationError,
            anthropic.PermissionDeniedError,
            anthropic.NotFoundError,
        ) as erreur:
            raise Fatale(str(erreur)) from erreur

        bloc_outil = next((bloc for bloc in message.content if bloc.type == "tool_use"), None)
        if bloc_outil is None:
            raise SortieInvalide("aucun bloc tool_use dans la reponse")

        try:
            instance = schema.model_validate(bloc_outil.input)
        except ValidationError as erreur:
            raise SortieInvalide(str(erreur)) from erreur

        usage = message.usage
        return Reponse(
            texte=instance.model_dump_json(),
            modele=message.model,
            tokens_entree=usage.input_tokens if usage else 0,
            tokens_sortie=usage.output_tokens if usage else 0,
        )
