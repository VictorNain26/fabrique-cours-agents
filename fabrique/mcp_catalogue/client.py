"""Client MCP de la fabrique : le graphe resout les prix par le protocole.

Connexion en memoire au serveur du catalogue (`mcp.Client` accepte une
instance `MCPServer`, docstring de mcp 2.2.0). Appele depuis du code
synchrone : l'API execute ses routes `def` dans un pool de threads, ou aucune
boucle asyncio ne tourne.
"""

from __future__ import annotations

import asyncio

from mcp import Client

from fabrique.mcp_catalogue.serveur import MESSAGE_REFERENCE_INCONNUE, PrixResolu, construire


async def _resoudre(reference: str) -> PrixResolu | None:
    async with Client(construire()) as client:
        resultat = await client.call_tool("resoudre_prix", {"reference": reference})
    if resultat.is_error:
        error_text = resultat.content[0].text
        if MESSAGE_REFERENCE_INCONNUE in error_text:
            return None
        raise RuntimeError(error_text)
    return PrixResolu.model_validate(resultat.structured_content)


def resoudre_prix(reference: str) -> PrixResolu | None:
    return asyncio.run(_resoudre(reference))
