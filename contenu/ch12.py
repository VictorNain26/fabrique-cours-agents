from __future__ import annotations

import inspect

from contenu.commun import C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 12. Livraison et non-regression
# ═════════════════════════════════════════════════════════════════════════ #

SQ12 = '''
"""Porte de non-regression appelee par l'integration continue.

Rejoue le golden dataset avec le fournisseur factice, compare les scores a la
reference versionnee dans le depot, et sort en erreur si la qualite recule.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from langgraph.checkpoint.memory import InMemorySaver

from fabrique.evaluation.dataset import CAS
from fabrique.evaluation.experience import exiger_non_regression, lancer_local
from fabrique.generation.graphe import construire
from fabrique.providers.fake import FournisseurFake

REFERENCE = Path(__file__).parent / "reference.json"
MARGE = 0.05


def tache(*, item, **_):
    # Construis un graphe avec FournisseurFake(), l'ensemble des pages
    # existantes tire de item["metadata"]["pages_existantes"], et un
    # checkpointer InMemorySaver(). Invoque-le avec le brief item["input"] et
    # un thread_id egal a item["metadata"]["identifiant"]. Renvoie
    # etat.get("page").
    raise NotImplementedError


def main() -> int:
    # 1. Rejoue CAS avec `tache` via lancer_local, recupere candidat["moyennes"].
    # 2. Si REFERENCE n'existe pas encore : ecris-la (json indente, cles triees)
    #    depuis ce run, affiche les moyennes, renvoie 0.
    # 3. Sinon : charge la reference, affiche un tableau reference/candidat,
    #    appelle exiger_non_regression(reference, candidat, MARGE) -- elle leve
    #    RegressionError en cas de regression -- puis renvoie 0.
    raise NotImplementedError


if __name__ == "__main__":
    sys.exit(main())
'''


def verif12(m):
    import contextlib
    import io
    import json

    tache = ok(m, "tache")
    main = ok(m, "main")
    res = []

    params = inspect.signature(tache).parameters
    item_param = params.get("item")
    res.append(
        (
            item_param is not None and item_param.kind == inspect.Parameter.KEYWORD_ONLY,
            "tache a un parametre keyword-only nomme item",
        ),
    )

    marge = getattr(m, "MARGE", None)
    res.append((isinstance(marge, float) and marge > 0, "MARGE est un float strictement positif"))

    reference = getattr(m, "REFERENCE", None)
    res.append(
        (reference is not None and reference.exists(), "REFERENCE pointe sur un fichier existant")
    )
    if reference is not None and reference.exists():
        contenu = json.loads(reference.read_text())
        res.append(("moyennes" in contenu, "le contenu de REFERENCE a une cle 'moyennes'"))

    tampon = io.StringIO()
    with contextlib.redirect_stdout(tampon):
        code = main()
    res.append((code == 0, "main() renvoie 0 quand la reference correspond au run courant"))
    return res


CH12 = Chapitre(
    numero=12,
    titre="Livraison et non-regression",
    objectif="empecher une regression de qualite d'atteindre la production",
    duree_min=25,
    blocs=[
        T(
            "Le chapitre 7 t'a donne verdict() et la notion d'ecart sous une marge. Ce "
            "chapitre branche cette logique sur l'integration continue, pour qu'elle "
            "s'applique a chaque pull request sans dependre de la memoire de qui que ce "
            "soit."
        ),
        H("Pourquoi une porte en CI, pas dans une tete"),
        T(
            "Une regression detectee a l'oeil suppose que quelqu'un ait pense a rejouer le "
            "dataset avant de merger, et qu'il ait le seuil en tete. Une porte en CI ne "
            "l'oublie jamais, tourne sur chaque pull request, et bloque le merge avant que "
            "la regression n'atteigne main. `fabrique/evaluation/reference.json` est "
            "commite dans le depot, pas genere a la volee : une pull request qui fait "
            "bouger les scores doit aussi toucher ce fichier, et ce changement se relit en "
            "revue de code comme n'importe quel autre changement de logique metier."
        ),
        H("Le module fabrique.evaluation.ci"),
        C("""REFERENCE = Path(__file__).parent / "reference.json"
MARGE = 0.05

def tache(*, item, **_):
    graphe = construire(FournisseurFake(), pages_existantes, checkpointer=InMemorySaver())
    etat = graphe.invoke({"brief": item["input"], "essais": 0}, config=...)
    return etat.get("page")

def main() -> int:
    candidat = {"moyennes": lancer_local(tache, CAS)["moyennes"]}
    exiger_non_regression(reference, candidat, MARGE)
    return 0"""),
        T(
            "`tache` rejoue le graphe LangGraph du chapitre 2 avec `FournisseurFake`, pas "
            "avec un vrai fournisseur : deterministe, gratuit, pas de reseau. `main` compare "
            "les moyennes obtenues a `reference.json`, et laisse `exiger_non_regression` "
            "lever `RegressionError` si un score recule au dela de `MARGE`. Avec "
            "MARGE=0.05, un ecart de -0.03 n'est ni une amelioration ni une regression : "
            '`verdict()` renvoie "indecis", et `exiger_non_regression` ne leve pas. '
            "Vouloir trancher sous la marge, sur un dataset de vingt a trente cas, est "
            "l'erreur la plus frequente en lecture de metriques."
        ),
        H("Ce que la CI du depot fait reellement"),
        C("""lint      ruff check .
format    ruff format --check .
tests     pytest -q
porte     python -m fabrique.evaluation.ci"""),
        T(
            "Quatre etapes dans cet ordre, lues dans .github/workflows/ci.yml. Le lint et "
            "le format cassent vite et pas cher, donc en premier. Les tests unitaires "
            "ensuite. La porte de non-regression en dernier, parce qu'elle est la plus "
            "lente : elle rejoue tout le golden dataset a travers le graphe complet."
        ),
        H("Le conteneur : non-root, healthcheck, dependance conditionnelle"),
        T(
            "Le Dockerfile installe les dependances, copie fabrique/, cree un utilisateur "
            "non-root (`useradd --create-home --uid 1000 fabrique` puis `USER fabrique`) et "
            "declare un HEALTHCHECK qui interroge `/sante` toutes les 30 secondes. "
            "docker-compose.yml ajoute un service Postgres avec son propre healthcheck "
            "(`pg_isready`), et l'API ne demarre que quand `base` est `service_healthy` -- "
            "une dependance conditionnelle, pas juste un ordre de demarrage. Description "
            "faite en lisant les deux fichiers du depot tels quels, pas de memoire "
            "generique sur Docker."
        ),
        H("Une limite honnete"),
        T(
            "La porte de non-regression ne tourne qu'avec `FournisseurFake`. Les "
            "adaptateurs OVHcloud et Anthropic ne sont pas couverts par la CI, faute de cle "
            "API disponible dans l'environnement de build. Un changement qui casse "
            "specifiquement l'un de ces deux fournisseurs passera la CI sans etre detecte. "
            "C'est une limite reelle du dispositif actuel, a annoncer plutot qu'a taire."
        ),
    ],
    questions=[
        Question(
            enonce="Un score de candidat est 0.94, la reference est 0.97, MARGE=0.05. "
            "Que fait exiger_non_regression ?",
            options=[
                "Elle leve RegressionError",
                "Elle ne leve pas : l'ecart de 0.03 est sous la marge, verdict indecis",
                "Elle ecrit une nouvelle reference automatiquement",
                "Elle leve seulement si tous les scores reculent",
            ],
            bonne=1,
            explication="0.03 < MARGE=0.05 : verdict indecis, pas de regression averee, "
            "exiger_non_regression ne leve pas.",
            source="execute",
        ),
        Question(
            enonce="Pourquoi reference.json est-il versionne dans le depot plutot que "
            "regenere a chaque run ?",
            options=[
                "Pour gagner du temps de calcul",
                "Pour qu'un changement de seuil se relise explicitement en revue de code",
                "Parce que Langfuse l'exige",
                "Ce n'est pas versionne, il est regenere a chaque CI",
            ],
            bonne=1,
            explication="Un fichier commite rend visible et relisable tout changement de "
            "seuil, au meme titre qu'un changement de code.",
            source="auteur",
        ),
        Question(
            enonce="Quels fournisseurs sont couverts par la porte de non-regression en CI ?",
            options=[
                "OVHcloud et Anthropic",
                "Seulement le fournisseur factice",
                "Les trois, avec des cles de test",
                "Aucun, la porte tourne sans fournisseur",
            ],
            bonne=1,
            explication="Seul FournisseurFake tourne en CI, faute de cle API OVHcloud ou "
            "Anthropic dans l'environnement de build.",
            source="auteur",
        ),
    ],
    kata=Kata(
        module="fabrique.evaluation.ci",
        consigne="Ecris la porte de non-regression appelee par la CI. `tache` doit "
        "rejouer le graphe avec le fournisseur factice, `main` doit rejouer tout "
        "le golden dataset, comparer a reference.json et lever via "
        "exiger_non_regression si la qualite recule.",
        squelette=SQ12,
        verifier=verif12,
        indice="tache construit le graphe avec construire(FournisseurFake(), "
        'set(item["metadata"]["pages_existantes"]), checkpointer=InMemorySaver()), '
        'l\'invoque avec {"brief": item["input"], "essais": 0} et un thread_id egal '
        'a item["metadata"]["identifiant"], puis renvoie etat.get("page"). main '
        "appelle lancer_local(tache, CAS) pour obtenir candidat, ecrit la reference "
        "si elle est absente, sinon appelle exiger_non_regression(reference, "
        "candidat, MARGE) et renvoie 0.",
        dependances=["langgraph", "langfuse"],
    ),
    entretien=[
        "Explique pourquoi la porte de non-regression tourne en dernier dans le "
        "pipeline de CI, apres le lint, le format et les tests.",
        "Un score recule de 0.02 sous une marge de 0.05. Que repond la porte, et "
        "pourquoi ce n'est pas un bug.",
        "Quelle est la limite actuelle de cette porte concernant les fournisseurs "
        "OVHcloud et Anthropic, et que ferais-tu pour la reduire.",
    ],
    sources=[
        Source(
            "auteur",
            "Le principe : une porte de non-regression vit en CI, pas dans "
            "une revue humaine ponctuelle",
        ),
        Source(
            "execute",
            "Contenu de .github/workflows/ci.yml lu tel quel : lint ruff, "
            "format ruff, pytest, puis python -m fabrique.evaluation.ci",
        ),
        Source(
            "execute",
            "Dockerfile et docker-compose.yml lus tels quels : utilisateur "
            "non-root, healthcheck sur /sante, Postgres avec pg_isready et depends_on "
            "condition service_healthy",
        ),
        Source("auteur", "La limite de couverture CI sur les fournisseurs OVHcloud et Anthropic"),
    ],
)
