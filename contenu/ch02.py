from __future__ import annotations

from pathlib import Path

from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 2. LangGraph : le vrai StateGraph
# ═════════════════════════════════════════════════════════════════════════ #

SQ2 = '''
"""Graphe LangGraph de la fabrique : redaction, controle, correction, validation
humaine, publication."""

from __future__ import annotations

from typing import Callable, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Overwrite, RetryPolicy, interrupt

from fabrique.garde_fous.validateur import bloquantes, valider
from fabrique.generation.reparation import generer_valide
from fabrique.modeles import EtatPage, Page, Violation
from fabrique.providers.base import Fournisseur, SortieInvalide, Surcharge

SYSTEME = "Tu generes une page web au format JSON strict conforme au schema fourni."


def _publier_neutre(page: Page) -> str:
    return "publication-neutre"


def construire(
    fournisseur: Fournisseur,
    pages_existantes: set[str],
    *,
    checkpointer=None,
    max_tours: int = 3,
    publier: Callable[[Page], str] = _publier_neutre,
) -> CompiledStateGraph:
    # Le graphe a construire :
    #
    #   START -> redaction -> controle
    #   apres "controle", arete conditionnelle :
    #        "correction"          s'il reste des violations BLOQUANTES et essais < max_tours
    #        "validation_humaine"  sinon
    #   correction -> redaction
    #   apres "validation_humaine", arete conditionnelle :
    #        "publication" si approuve, sinon END
    #   publication -> END
    #
    # Ce que fait chaque noeud :
    #   redaction          essais + 1, appelle generer_valide(...) avec le schema Page,
    #                      range la page en dict. Pose un retry_policy explicite dessus.
    #   controle           appelle valider(...) et range les violations en dicts
    #   correction         AUCUN appel LLM : fabrique un retour actionnable a partir des
    #                      violations bloquantes. Le journal a un reducteur qui CONCATENE,
    #                      donc renvoyer une liste ne l'efface pas : il faut Overwrite.
    #   validation_humaine UNIQUEMENT interrupt({...}). La reponse attendue est
    #                      {"approuve": bool, "commentaire": str}. Rien d'autre ici.
    #   publication        le seul noeud a effet de bord : appelle publier(page).
    #
    # Pourquoi publication est un noeud separe : un noeud qui contient un interrupt()
    # est rejoue DEPUIS LE DEBUT a la reprise. Publier dans ce noeud publierait deux fois.
    raise NotImplementedError
'''


def verif2(m):
    from langgraph.checkpoint.memory import InMemorySaver

    from fabrique.modeles import BlocPage, Page
    from fabrique.providers.base import Reponse

    construire = ok(m, "construire")
    res = []

    def page_json(nb_titres=1, prix=False):
        blocs = [{"type": "titre", "contenu": f"T{i}"} for i in range(nb_titres)]
        if prix:
            blocs.append({"type": "paragraphe", "contenu": "a partir de 4,99 EUR"})
        return Page(
            titre_h1="VPS",
            meta_description="d" * 130,
            blocs=[BlocPage(**b) for b in blocs],
            liens=[],
        ).model_dump_json()

    class FauxFournisseur:
        nom = "faux"
        cout_par_appel = 0.0

        def __init__(self, textes):
            self.textes = list(textes)
            self.appels = 0

        def generer(self, *, invite, schema, systeme="", retour=None):
            texte = self.textes[min(self.appels, len(self.textes) - 1)]
            self.appels += 1
            return Reponse(texte=texte, modele="faux")

    publiees = []
    f = FauxFournisseur([page_json(nb_titres=2), page_json(nb_titres=1)])
    g = construire(
        [f], set(), checkpointer=InMemorySaver(), publier=lambda p: publiees.append(p) or "pub"
    )
    res.append((hasattr(g, "invoke"), "construire renvoie un graphe compile"))

    noeuds = set(g.get_graph().nodes)
    attendus = {"redaction", "controle", "correction", "validation_humaine", "publication"}
    res.append((attendus <= noeuds, f"les cinq noeuds sont declares (vu {sorted(noeuds)})"))

    cfg = {"configurable": {"thread_id": "k2-a"}}
    etat = g.invoke({"brief": "page vps", "essais": 0}, config=cfg)
    res.append(
        (
            etat.get("essais") == 2,
            f"la correction a relance la redaction (essais={etat.get('essais')})",
        )
    )
    res.append(("__interrupt__" in etat, "le graphe s'interrompt pour la validation humaine"))
    res.append(
        (
            g.get_state(cfg).next == ("validation_humaine",),
            "l'execution attend bien sur validation_humaine",
        )
    )
    res.append((publiees == [], "rien n'est publie avant l'approbation"))

    from langgraph.types import Command

    fin = g.invoke(Command(resume={"approuve": True, "commentaire": ""}), config=cfg)
    res.append((fin.get("publiee") is True, "la reprise approuvee publie la page"))
    res.append((len(publiees) == 1, f"publier appele exactement une fois ({len(publiees)})"))

    f2 = FauxFournisseur([page_json(nb_titres=1)])
    pub2 = []
    g2 = construire(
        [f2], set(), checkpointer=InMemorySaver(), publier=lambda p: pub2.append(p) or "pub"
    )
    cfg2 = {"configurable": {"thread_id": "k2-b"}}
    g2.invoke({"brief": "x", "essais": 0}, config=cfg2)
    g2.invoke(Command(resume={"approuve": False, "commentaire": "non"}), config=cfg2)
    res.append((pub2 == [], "un refus ne publie pas"))

    f3 = FauxFournisseur([page_json(nb_titres=2)])
    g3 = construire([f3], set(), checkpointer=InMemorySaver(), max_tours=2)
    cfg3 = {"configurable": {"thread_id": "k2-c"}}
    e3 = g3.invoke({"brief": "x", "essais": 0}, config=cfg3)
    res.append(
        (e3.get("essais") == 2, f"la borne max_tours arrete la boucle (essais={e3.get('essais')})")
    )

    src = Path(m.__file__).read_text()
    res.append(("Overwrite" in src, "Overwrite est utilise pour vider le journal"))
    res.append(("retry_policy" in src, "un retry_policy explicite est pose sur redaction"))
    return res


CH2 = Chapitre(
    numero=2,
    titre="LangGraph : le vrai StateGraph",
    objectif="ecrire un graphe avec boucle bornee, avec l'API reelle",
    duree_min=40,
    blocs=[
        T(
            "Version installee : langgraph 1.2.11. La 1.0 est sortie en octobre 2025 sans "
            "breaking change, et les primitives n'ont pas bouge depuis."
        ),
        H("Les trois composants, mot pour mot la doc"),
        T(
            "State : une structure de donnees partagee qui represente l'instantane courant "
            "de l'application. Nodes : des fonctions qui recoivent l'etat, calculent, et "
            "renvoient une mise a jour. Edges : des fonctions qui determinent quel noeud "
            "executer ensuite. La doc resume ainsi : les noeuds font le travail, les aretes "
            "disent quoi faire ensuite."
        ),
        T(
            "Le moteur procede par super-steps, inspires de Pregel. Les noeuds qui tournent "
            "en parallele appartiennent au meme super-step, ceux qui s'enchainent sont dans "
            "des super-steps differents."
        ),
        H("Le squelette reel"),
        C("""from typing import TypedDict
from langgraph.graph import END, START, StateGraph

class Etat(TypedDict):
    brief: str
    violations: list[str]
    essais: int

b = StateGraph(Etat)
b.add_node("redaction", redaction)
b.add_edge(START, "redaction")
b.add_conditional_edges("controle", router, [END, "correction"])
graphe = b.compile()          # obligatoire avant tout invoke"""),
        T(
            "Le schema d'etat peut etre un TypedDict, une dataclass si tu veux des valeurs "
            "par defaut, ou un modele Pydantic si tu veux la validation recursive. La doc "
            "precise que Pydantic est moins performant que TypedDict ou dataclass."
        ),
        H("Les reducteurs, et le piege que presque personne ne connait"),
        T(
            "Chaque cle de l'etat a son propre reducteur. Sans annotation, le reducteur par "
            "defaut ignore la valeur courante et la remplace par la mise a jour du noeud."
        ),
        C("""from operator import add
from typing import Annotated

class Etat(TypedDict):
    errors: Annotated[list[str], add]

# noeud A renvoie {"errors": ["bad sql"]}
# noeud B renvoie {"errors": []}
# state["errors"] vaut TOUJOURS ["bad sql"] : la liste vide est fusionnee, pas effacee"""),
        A(
            "Consequence documentee : avec un reducteur qui fusionne, renvoyer une valeur "
            "vide n'efface PAS le champ. Pour un compteur d'erreurs qu'il faut vider entre "
            "deux tentatives, il faut envelopper la mise a jour dans Overwrite, importe "
            "depuis langgraph.types. C'est exactement le cas d'une boucle de correction."
        ),
        H("Reprise et idempotence"),
        T(
            "Avec un checkpointer, LangGraph sauvegarde aux frontieres de super-step, pas au "
            "milieu d'une fonction. Si l'execution reprend apres une interruption ou un "
            "retry, le noeud concerne est REJOUE DEPUIS LE DEBUT de sa fonction : le code et "
            "les effets de bord situes avant la pause s'executent une seconde fois."
        ),
        T(
            "Donc la logique d'un noeud doit etre idempotente. Si un noeud insere une ligne "
            "en base, le rejouer ne doit pas creer de doublon. Cles d'idempotence, upserts, "
            "ou lecture avant ecriture."
        ),
        H("Limite de recursion"),
        T(
            "La limite de recursion par defaut vaut 10007 super-steps dans langgraph "
            "1.2.11, et le depassement leve GraphRecursionError. Le chiffre est lu dans "
            "l'environnement, donc il se change sans toucher au code : la constante vaut "
            'int(getenv("LANGGRAPH_DEFAULT_RECURSION_LIMIT", "10007")). Par appel, elle '
            "se passe dans config a la racine, pas dans configurable."
        ),
        A(
            "Beaucoup de tutoriels citent 25, et beaucoup d'autres 1000. Les deux sont des "
            "valeurs d'anciennes versions. Verifie toujours contre la version que tu as "
            "installee : c'est le genre de chiffre qu'on recite de memoire et qu'on rate."
        ),
        A(
            "La limite de recursion n'est pas ta borne metier. Elle protege le moteur. Ta "
            "borne a toi vit dans l'etat, sous forme de compteur d'essais lu par l'arete "
            "conditionnelle. C'est ce que tu vas ecrire."
        ),
    ],
    questions=[
        Question(
            enonce='Avec Annotated[list, operator.add], un noeud renvoie {"errors": []}. '
            "Que vaut l'etat ?",
            options=[
                "Il est vide, la liste a ete remplacee",
                "Il garde les valeurs precedentes, la liste vide est fusionnee",
                "Le moteur leve une erreur",
                "Cela depend de l'ordre des noeuds",
            ],
            bonne=1,
            explication="Piege documente. Pour vider le champ tout en gardant le "
            "reducteur, il faut Overwrite([]) depuis langgraph.types.",
            source="doc Graph API overview, section Resetting a reducer field",
        ),
        Question(
            enonce="Un noeud est rejoue apres une interruption. Que se passe-t-il ?",
            options=[
                "Il reprend a l'instruction exacte ou il s'etait arrete",
                "Il repart du debut de sa fonction, effets de bord compris",
                "Il est saute car deja execute",
                "Le graphe redemarre entierement",
            ],
            bonne=1,
            explication="Les checkpoints sont poses aux frontieres de super-step, pas au "
            "milieu d'une fonction. D'ou l'exigence d'idempotence des noeuds.",
            source="doc Graph API overview, section Re-execution and idempotency",
        ),
        Question(
            enonce="Limite de recursion par defaut en langgraph 1.2.11 ?",
            options=["25", "1000", "10007", "illimitee"],
            bonne=2,
            explication="10007 super-steps, puis GraphRecursionError. Lu dans "
            "langgraph/_internal/_config.py : DEFAULT_RECURSION_LIMIT = "
            'int(getenv("LANGGRAPH_DEFAULT_RECURSION_LIMIT", "10007")). '
            "25 et 1000 sont des valeurs d'anciennes versions, encore "
            "largement recopiees en ligne.",
            source="verifie en executant langgraph 1.2.11",
        ),
    ],
    kata=Kata(
        module="fabrique.generation.graphe",
        consigne="Construis le graphe de la fabrique. Boucle de correction bornee, "
        "interruption pour la validation humaine, et publication dans un "
        "noeud separe. Le correcteur execute reellement le graphe, l'arrete "
        "sur l'interruption, le reprend, et verifie que la publication n'a "
        "lieu qu'une seule fois.",
        squelette=SQ2,
        verifier=verif2,
        indice='add_conditional_edges("controle", route) suffit quand la fonction de '
        "route est annotee Literal[...]. Pour vider le journal malgre son "
        'reducteur : return {"journal": Overwrite(value=[retour])}. '
        "interrupt() exige un checkpointer et un thread_id dans config.",
        dependances=["langgraph", "pydantic"],
    ),
    entretien=[
        "Explique LangGraph en trois phrases sans citer une fonction de son API.",
        "Dis dans quel cas tu ne le mettrais pas.",
        "Explique pourquoi un noeud doit etre idempotent.",
    ],
    sources=[
        Source(
            "doc",
            "Graph API overview, LangChain",
            "https://docs.langchain.com/oss/python/langgraph/graph-api",
        ),
        Source(
            "recherche",
            "LangChain 1.0 et LangGraph 1.0",
            "https://www.langchain.com/blog/langchain-langgraph-1dot0",
        ),
        Source("execute", "langgraph 1.2.11 installe, graphe compile et execute"),
        Source("execute", "DEFAULT_RECURSION_LIMIT=10007, _internal/_config.py ligne 32"),
    ],
)
