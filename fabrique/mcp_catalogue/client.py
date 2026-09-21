"""Client MCP de la fabrique : le graphe resout les prix par le protocole.

Connexion en memoire au serveur du catalogue (`mcp.Client` accepte une
instance `MCPServer`, docstring de mcp 2.2.0). Appele depuis du code
synchrone : l'API execute ses routes `def` dans un pool de threads, ou aucune
boucle asyncio ne tourne. D'autres appelants synchrones tournent pourtant
dans une boucle deja lancee (la tache d'une experience Langfuse, par
exemple), ou `asyncio.run` refuse de demarrer : la resolution part alors
dans un thread a part, qui a sa propre boucle.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from mcp import Client

from fabrique.mcp_catalogue.serveur import MESSAGE_REFERENCE_INCONNUE, PrixResolu, construire


class CatalogueIndisponible(Exception):
    """Le catalogue a plante : ce n'est pas une reference inconnue."""


async def _resoudre(reference: str) -> PrixResolu | None:
    async with Client(construire()) as client:
        resultat = await client.call_tool("resoudre_prix", {"reference": reference})
    if resultat.is_error:
        error_text = resultat.content[0].text
        if MESSAGE_REFERENCE_INCONNUE in error_text:
            return None
        raise CatalogueIndisponible(error_text)
    return PrixResolu.model_validate(resultat.structured_content)


def resoudre_prix(reference: str) -> PrixResolu | None:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_resoudre(reference))
    with ThreadPoolExecutor(max_workers=1) as executeur:
        return executeur.submit(asyncio.run, _resoudre(reference)).result()
