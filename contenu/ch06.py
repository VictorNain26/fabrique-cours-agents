from __future__ import annotations

import asyncio

from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 6. MCP : un vrai serveur
# ═════════════════════════════════════════════════════════════════════════ #

SQ6 = """
# Atelier 6 — un vrai serveur MCP (SDK mcp 2.2.0).
# ATTENTION : en mcp 2.x, FastMCP a ete renomme MCPServer.
from __future__ import annotations

from mcp.server import MCPServer
from pydantic import BaseModel

from fabrique.mcp_catalogue import catalogue
from fabrique.mcp_catalogue.catalogue import Produit


class PrixResolu(BaseModel):
    reference: str
    prix_mensuel_eur: float
    libelle_affichable: str


def construire() -> MCPServer:
    # Construis et renvoie un MCPServer nomme "catalogue-hebergeur" exposant
    # TROIS outils :
    #
    # 1. chercher_produit(requete_en_langage_naturel: str) -> list[Produit]
    # 2. get_produit(reference: str) -> Produit | None
    # 3. resoudre_prix(reference: str) -> PrixResolu
    #
    # catalogue.chercher(requete) -> list[Produit]
    # catalogue.get(reference) -> Produit | None
    #
    # Le correcteur verifie que :
    #   - les trois outils sont exposes avec ces noms exacts
    #   - chaque description fait plus de 60 caracteres et dit quand NE PAS
    #     utiliser l'outil (le mot "pas" doit y figurer)
    #   - aucun nom de parametre ne fait moins de 4 caracteres
    #   - le schema d'entree genere marque les parametres comme requis
    #   - resoudre_prix("vps-starter") renvoie le prix reel du catalogue
    #
    # Rappel : le SDK derive le schema des annotations de type, et la
    # description de la docstring. La docstring EST le prompt de l'outil.
    raise NotImplementedError
"""


def verif6(m):
    construire = ok(m, "construire")
    s = construire()
    res = []

    from fabrique.mcp_catalogue import catalogue

    async def sonder():
        outils = await s.list_tools()
        r = await s.call_tool("resoudre_prix", {"reference": "vps-starter"})
        return outils, r

    outils, resultat = asyncio.run(sonder())
    par_nom = {t.name: t for t in outils}
    noms_attendus = {"chercher_produit", "get_produit", "resoudre_prix"}

    res.append(
        (noms_attendus <= set(par_nom), f"les trois outils sont exposes (vu: {sorted(par_nom)})"),
    )
    if noms_attendus <= set(par_nom):
        for nom, t in par_nom.items():
            d = t.description or ""
            res.append((len(d) > 60, f"{nom} : description assez detaillee ({len(d)} car.)"))
            res.append(("pas" in d.lower(), f"{nom} : la description dit quand NE PAS l'utiliser"))
            props = list((t.input_schema or {}).get("properties", {}))
            res.append(
                (all(len(p) >= 4 for p in props), f"{nom} : parametres explicites {props}"),
            )
            res.append(
                (
                    bool((t.input_schema or {}).get("required")),
                    f"{nom} : le schema marque les parametres requis",
                ),
            )
        produit = catalogue.get("vps-starter")
        prix = resultat.structured_content or {}
        res.append(
            (
                prix.get("prix_mensuel_eur") == produit.prix_mensuel_eur,
                "resoudre_prix renvoie le prix reel du catalogue",
            ),
        )
    return res


CH6 = Chapitre(
    numero=6,
    titre="MCP : un vrai serveur",
    objectif="exposer des outils qu'un agent appelle correctement",
    duree_min=35,
    blocs=[
        T(
            "Version installee : mcp 2.2.0. Premier fait a connaitre, et il est recent : en "
            "mcp 2.x, FastMCP a ete renomme MCPServer. Le message d'erreur du SDK renvoie "
            "vers un guide de migration et propose d'epingler mcp<2 pour garder du code v1. "
            "Beaucoup de tutoriels en ligne sont donc perimes."
        ),
        C("""# mcp 1.x
from mcp.server.fastmcp import FastMCP
# mcp 2.x
from mcp.server.mcpserver import MCPServer"""),
        H("Etat du protocole"),
        T(
            "La revision courante de la specification est 2026-07-28, la plus grosse depuis "
            "le lancement : coeur du protocole stateless, ce qui fait qu'un serveur distant "
            "redevient un workload HTTP ordinaire, cadre d'extensions gouvernees, extension "
            "Tasks pour le travail long, MCP Apps, autorisation alignee sur OAuth 2.0 et "
            "OpenID Connect, et politique de depreciation formelle avec douze mois minimum "
            "entre depreciation et retrait. La revision precedente etait 2025-11-25, et la "
            "sortie structuree des outils date de 2025-06-18. La version est negociee a "
            "l'initialisation."
        ),
        H("La docstring est le prompt"),
        T(
            "Le SDK derive le schema d'entree des annotations de type et la description de la "
            "docstring. Verifie dans le venv du cours : une fonction annotee reference: str "
            "produit un schema JSON avec properties.reference de type string et required "
            "[reference]."
        ),
        C('''@s.tool()
def get_produit(reference: str) -> str:
    """Renvoie la fiche technique d'un produit OVHcloud a partir de sa reference
    exacte. N'utilise pas cet outil avec un nom commercial : passe d'abord par
    chercher_produit."""
    ...

# schema genere, observe reellement :
# {"properties": {"reference": {"title": "Reference", "type": "string"}},
#  "required": ["reference"], "type": "object"}'''),
        T(
            "Le nom du parametre travaille autant que la description. Un parametre q se "
            "remplit mal, requete_en_langage_naturel se remplit bien. Et dire explicitement "
            "quand ne pas utiliser l'outil evite une grande partie des mauvais appels."
        ),
        H("Ce que fait le SDK quand l'appel est mauvais"),
        T(
            "Observe dans le venv : appeler get_produit sans son argument requis leve une "
            "ToolError cote serveur, construite a partir de la ValidationError Pydantic, avec "
            "le detail du champ manquant. Autrement dit la validation d'arguments est deja "
            "faite pour toi, et le message est exploitable par un modele."
        ),
        A(
            "Un serveur MCP tiers injecte du texte dans ton contexte. C'est une surface "
            "d'injection de prompt et d'exfiltration. Chez un hebergeur, mentionner ce risque "
            "sans qu'on te le demande vaut tres cher."
        ),
        H("L'enveloppe result"),
        T(
            "Observe dans le venv du cours : un outil annote pour renvoyer un modele Pydantic "
            "direct produit un structured_content egal au dict du modele. Un outil annote "
            'list[X] ou X | None voit sa sortie enveloppee dans {"result": ...}. La forme '
            "depend de l'annotation de retour, pas du contenu : lis toujours structured_content "
            "plutot que de deviner sa forme a partir du type Python."
        ),
        C("""# structured_content observe reellement (mcp 2.2.0)
resoudre_prix(reference) -> PrixResolu   =>  {"reference": ..., "prix_mensuel_eur": ...}
chercher_produit(...) -> list[Produit]   =>  {"result": [ {...}, {...} ]}
get_produit(...) -> Produit | None       =>  {"result": {...}}  ou  {"result": None}"""),
        H("Le nombre d'outils"),
        T(
            "Au dela de quelques dizaines d'outils aux frontieres floues, la selection se "
            "degrade. Trois parades : restreindre l'ensemble visible selon l'etape, deleguer "
            "a des sous-agents, ou regrouper derriere un outil unique qui prend une "
            "intention. Position d'auteur, pas une citation."
        ),
    ],
    questions=[
        Question(
            enonce="Tu reprends un tutoriel qui fait `from mcp.server.fastmcp import "
            "FastMCP` avec mcp 2.x. Que se passe-t-il ?",
            options=[
                "Ca marche, c'est un alias",
                "ModuleNotFoundError : FastMCP a ete renomme MCPServer",
                "Un avertissement de depreciation",
                "Ca marche mais sans les outils",
            ],
            bonne=1,
            explication="Le SDK leve une ModuleNotFoundError avec un message qui renvoie au "
            "guide de migration et suggere d'epingler mcp<2.",
            source="verifie en executant mcp 2.2.0",
        ),
        Question(
            enonce="Revision courante de la specification MCP ?",
            options=["2025-03-26", "2025-06-18", "2025-11-25", "2026-07-28"],
            bonne=3,
            explication="2026-07-28 : coeur stateless, extensions, Tasks, MCP Apps, "
            "autorisation durcie.",
            source="modelcontextprotocol.io/specification/2026-07-28",
        ),
        Question(
            enonce="D'ou vient le schema d'entree d'un outil dans le SDK Python ?",
            options=[
                "D'un fichier JSON separe",
                "Des annotations de type de la fonction",
                "Il faut l'ecrire a la main",
                "Il est devine par le modele",
            ],
            bonne=1,
            explication="Annotations pour le schema, docstring pour la description. "
            "Verifie en executant le SDK.",
            source="verifie en executant mcp 2.2.0",
        ),
    ],
    kata=Kata(
        module="fabrique.mcp_catalogue.serveur",
        consigne="Ecris le serveur MCP de la fabrique, avec ses trois outils. Le "
        "correcteur demarre le serveur en memoire, liste les outils et en appelle "
        "un. Il verifie aussi la qualite des descriptions, parce que c'est ce qui "
        "determine le taux d'appel correct.",
        squelette=SQ6,
        verifier=verif6,
        indice='s = MCPServer("catalogue-hebergeur") puis @s.tool() au dessus de chaque '
        "fonction. La docstring doit contenir le mot 'pas' dans une phrase du type "
        "'Ne pas utiliser cet outil pour...'. resoudre_prix leve ValueError si la "
        "reference est inconnue au catalogue.",
        dependances=["mcp"],
    ),
    entretien=[
        "Montre une bonne et une mauvaise description d'outil, explique l'ecart.",
        "Cite un risque de securite propre aux serveurs MCP tiers.",
        "Dis ou en est la specification et ce qu'a change la derniere revision.",
    ],
    sources=[
        Source("execute", "mcp 2.2.0 : MCPServer, list_tools, call_tool, schema genere"),
        Source(
            "execute",
            "mcp 2.2.0 : structured_content et l'enveloppe result pour les retours list/optional",
        ),
        Source(
            "recherche",
            "Specification MCP 2026-07-28",
            "https://modelcontextprotocol.io/specification/2026-07-28",
        ),
        Source(
            "recherche",
            "Versioning de la specification",
            "https://modelcontextprotocol.io/specification",
        ),
        Source("auteur", "Les parades au trop grand nombre d'outils"),
    ],
)
