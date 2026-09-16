from __future__ import annotations

import ast
from pathlib import Path

from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 4. Temporal : workflow deterministe reel
# ═════════════════════════════════════════════════════════════════════════ #

SQ4 = '''
"""Workflow Temporal deterministe : le chemin automatique de la fabrique.

Redaction -> controle -> correction -> redaction, borne a 3 tours, puis
publication. Pas de validation humaine ici : c'est le role de LangGraph dans
ce projet, Temporal orchestre le chemin automatique jusqu'a la publication.

Aucune route de l'API ne demarre ce workflow : il est exerce par
tests/test_temporal.py et par soumission manuelle au worker.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from fabrique.temporal.activites import controler_page, generer_page, publier_page

TIMEOUT_GENERATION = timedelta(seconds=60)
TIMEOUT_CONTROLE = timedelta(seconds=10)
TIMEOUT_PUBLICATION = timedelta(seconds=30)

RETRY_ACTIVITE = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=2.0,
    maximum_attempts=3,
)


@workflow.defn
class GenerationPage:
    @workflow.run
    async def run(self, brief: str, pages_existantes: list[str]) -> dict:
        # A_ECRIRE. Contraintes de determinisme :
        #   - interdit : datetime.now(), time.time(), random.*, uuid.uuid4(),
        #     tout appel reseau direct, toute mutation d'etat global
        #   - autorise : workflow.now(), workflow.uuid4(), workflow.logger,
        #     et l'appel d'activities
        #
        # Ton run doit :
        #   1. horodater le demarrage avec l'API sure du SDK (workflow.now())
        #   2. boucler au plus 3 fois : generer_page, puis controler_page ; si
        #      des violations bloquantes restent et qu'il reste des tours,
        #      reinjecter leur detail dans le prochain generer_page
        #   3. chaque workflow.execute_activity doit avoir un
        #      start_to_close_timeout ET une retry_policy explicite
        #   4. sans violation bloquante, publier via publier_page avec une cle
        #      d'idempotence tiree de workflow.uuid4() (jamais uuid.uuid4())
        #   5. renvoyer un dict avec au moins "page", "violations", "publiee"
        raise NotImplementedError
'''

INTERDITS = {
    "datetime.now",
    "datetime.utcnow",
    "time.time",
    "random.random",
    "random.randint",
    "random.choice",
    "uuid.uuid4",
    "requests.get",
    "requests.post",
    "os.urandom",
}


def _appels(noeud):
    """Noms pointes de tous les appels dans un arbre AST."""
    out = []
    for n in ast.walk(noeud):
        if isinstance(n, ast.Call):
            f = n.func
            morceaux = []
            while isinstance(f, ast.Attribute):
                morceaux.append(f.attr)
                f = f.value
            if isinstance(f, ast.Name):
                morceaux.append(f.id)
            if morceaux:
                out.append(".".join(reversed(morceaux)))
    return out


def verif4(m):
    from temporalio import activity, workflow

    import fabrique.temporal.activites as activites

    res = []
    cls = ok(m, "GenerationPage")

    d_wf = workflow._Definition.from_class(cls)
    res.append((d_wf is not None, "GenerationPage est bien un workflow Temporal"))
    res.append(
        (
            d_wf is not None and d_wf.run_fn is not None,
            "la methode d'entree est marquee @workflow.run",
        ),
    )

    for nom_activite in ("generer_page", "controler_page", "publier_page"):
        fn = ok(activites, nom_activite)
        d_act = activity._Definition.from_callable(fn)
        res.append((d_act is not None, f"{nom_activite} est bien une activity Temporal"))

    chemin = getattr(m, "__file__", None)
    src_fichier = Path(chemin).read_text() if chemin else ""
    res.append(
        (
            "imports_passed_through" in src_fichier,
            "les imports d'activities passent par workflow.unsafe.imports_passed_through()",
        ),
    )

    corps = None
    for n in ast.walk(ast.parse(src_fichier)):
        if isinstance(n, ast.ClassDef) and n.name == "GenerationPage":
            corps = n
    res.append((corps is not None, "la classe GenerationPage est bien dans ton fichier"))
    appels = _appels(corps) if corps is not None else []
    src_corps = ast.get_source_segment(src_fichier, corps) or "" if corps is not None else ""

    fautifs = [a for a in appels if a in INTERDITS]
    res.append((not fautifs, f"aucun appel non deterministe dans le workflow ({fautifs})"))
    res.append(
        (
            any(a.endswith("workflow.now") or a == "now" for a in appels),
            "l'horodatage passe par workflow.now()",
        ),
    )
    res.append(
        (
            any(a.endswith("workflow.uuid4") or a == "uuid4" for a in appels),
            "la cle d'idempotence de publication vient de workflow.uuid4()",
        ),
    )
    nb_activites = sum(1 for a in appels if a.endswith("execute_activity"))
    res.append(
        (
            nb_activites >= 3,
            f"les trois activites sont appelees via workflow.execute_activity ({nb_activites}/3)",
        ),
    )
    res.append(("RetryPolicy(" in src_fichier, "une RetryPolicy explicite est definie"))
    nb_retry = src_corps.count("retry_policy=")
    res.append(
        (nb_retry >= 3, f"chaque appel d'activity recoit une retry_policy ({nb_retry}/3)"),
    )
    nb_timeout = src_corps.count("start_to_close_timeout")
    res.append(
        (nb_timeout >= 3, f"chaque appel d'activity a un start_to_close_timeout ({nb_timeout}/3)"),
    )
    return res


CH4 = Chapitre(
    numero=4,
    titre="Temporal : le workflow deterministe",
    objectif="ecrire un workflow qui survit au rejeu, avec l'API reelle",
    duree_min=40,
    blocs=[
        T(
            "Version installee : temporalio 1.33.0. C'est une des technos les plus exigeantes "
            "du cours, et celle ou une erreur de determinisme coute le plus cher en production."
        ),
        H("Pourquoi le determinisme"),
        T(
            "Le serveur Temporal peut rejouer ton workflow pour reconstruire son etat. Le "
            "code est donc reexecute depuis le debut, et doit emettre exactement la meme "
            "sequence de commandes. La doc parle de non-determinisme intrinseque quand le "
            "workflow peut emettre une sequence differente au rejeu, meme avec les memes "
            "entrees."
        ),
        H("La liste des interdits, mot pour mot"),
        C("""# Workflow code must be deterministic. This means:
#   no threading
#   no randomness
#   no external calls to processes
#   no network I/O
#   no global state mutation
#   no system date or time"""),
        T(
            "Ces six lignes viennent de la page Workflow Basics du SDK Python. Apprends-les "
            "telles quelles, elles structurent tout le reste du chapitre."
        ),
        H("Les alternatives sures fournies par le SDK"),
        C("""workflow.logger.info(...)     # au lieu de print ou logging
workflow.random().randint(1, 100)   # au lieu de random.random()
workflow.uuid4()                    # au lieu de uuid.uuid4()
workflow.now()                      # au lieu de datetime.now() ou time.time()"""),
        T(
            "workflow.now() renvoie l'heure de la derniere Workflow Task, ce qui est coherent "
            "d'un rejeu a l'autre. Le logger supprime automatiquement les messages pendant le "
            "rejeu, pour eviter les doublons dans tes logs."
        ),
        A(
            "workflow.unsafe.is_replaying existe pour garder du code qui ne doit tourner qu'a "
            "la premiere execution, typiquement l'emission d'une metrique. La doc met un "
            "avertissement explicite : ne jamais s'en servir pour modifier la logique metier, "
            "ca casse le determinisme."
        ),
        H("Le sandbox Python"),
        T(
            "Le SDK Python execute le code de workflow dans un sandbox, qui importe le "
            "fichier du workflow dans un environnement neuf et intercepte les appels "
            "non deterministes connus via des proxys. Ce n'est pas une isolation complete : "
            "certaines bibliotheques mutent leur etat interne et cassent quand meme le "
            "determinisme. D'ou le motif with workflow.unsafe.imports_passed_through() "
            "autour des imports d'activities et de modules tiers deterministes."
        ),
        H("Activities"),
        T(
            "Une activity est une fonction normale qui fait le travail sale : appel LLM, "
            "appel HTTP, ecriture en base. Elle s'execute hors du chemin de rejeu et elle "
            "est retentee automatiquement. La doc le dit explicitement pour l'IA : les "
            "appels LLM, l'usage d'outils et les etapes d'agent sont non deterministes par "
            "nature, donc ils vont dans des activities."
        ),
        A(
            "Une activity retentee peut s'executer deux fois. Idempotence obligatoire : cle "
            "d'idempotence cote CMS, upsert cote base. Publier deux fois la meme page parce "
            "que l'accuse de reception s'est perdu est le bug typique."
        ),
        H("Changement de code en cours de run"),
        T(
            "La doc distingue deux causes de non-determinisme : intrinseque, et les "
            "changements de code deployes alors que des executions sont encore actives. "
            "C'est le probleme que resout le versioning de workflow. Certains changements "
            "restent surs, par exemple modifier la duree d'un timer, sauf passage de ou vers "
            "zero en Python, Java et Go, ce qui est non deterministe."
        ),
    ],
    questions=[
        Question(
            enonce="Lequel n'est PAS dans la liste des interdits de la doc Python ?",
            options=[
                "no threading",
                "no network I/O",
                "no recursion",
                "no global state mutation",
            ],
            bonne=2,
            explication="La liste exacte : no threading, no randomness, no external calls "
            "to processes, no network I/O, no global state mutation, no system "
            "date or time. La recursion n'y est pas.",
            source="doc Workflow Basics, Python SDK",
        ),
        Question(
            enonce="A quoi sert workflow.unsafe.is_replaying ?",
            options=[
                "A brancher la logique metier selon le rejeu",
                "A garder du code qui ne doit tourner qu'a la premiere execution, comme "
                "une metrique",
                "A desactiver le sandbox",
                "A forcer un rejeu",
            ],
            bonne=1,
            explication="La doc met un avertissement explicite : ne jamais s'en servir "
            "pour affecter la logique metier, cela casse le determinisme.",
            source="doc Workflow Basics, section Detecting replay",
        ),
        Question(
            enonce="Un run est en cours, tu deploies du code qui change la sequence "
            "d'activities. Que se passe-t-il ?",
            options=[
                "Rien, le rejeu s'adapte",
                "Risque d'erreur de non-determinisme, d'ou le versioning de workflow",
                "Le run repart de zero",
                "Temporal bloque le deploiement",
            ],
            bonne=1,
            explication="C'est la seconde cause de non-determinisme citee par la doc : les "
            "changements de code deployes alors que des executions sont encore "
            "actives.",
            source="doc Workflow Definition, deterministic constraints",
        ),
    ],
    kata=Kata(
        module="fabrique.temporal.workflows",
        consigne="Ecris le corps de GenerationPage.run avec la vraie API temporalio, "
        "branche sur les vraies activities de fabrique.temporal.activites. Ce n'est "
        "pas un exercice : pendant cet atelier, ton fichier REMPLACE le module de "
        "l'app. Le correcteur verifie les decorateurs par introspection du SDK, puis "
        "analyse l'arbre syntaxique de ta classe pour y traquer les appels non "
        "deterministes. Aucun serveur Temporal requis pour ce correcteur (mais "
        "tests/test_temporal.py, lui, en lance un vrai en local via "
        "temporalio.testing.WorkflowEnvironment).",
        squelette=SQ4,
        verifier=verif4,
        indice="workflow.now() pour l'horodatage, workflow.uuid4() pour la cle "
        "d'idempotence de publication. await workflow.execute_activity(fn, "
        "args=[...], start_to_close_timeout=timedelta(...), "
        "retry_policy=RetryPolicy(...)). RetryPolicy vient de temporalio.common. "
        "Boucle bornee a 3 tours entre generer_page et controler_page.",
        dependances=["temporalio"],
    ),
    a_retenir=[
        "Les six contraintes de determinisme, et pourquoi chacune casse le rejeu.",
        "Pourquoi LangGraph et Temporal ne se remplacent pas.",
        "Dans quel cas Temporal serait surdimensionne.",
    ],
    sources=[
        Source(
            "doc",
            "Workflow Basics, Temporal Python SDK",
            "https://docs.temporal.io/develop/python/workflows/basics",
        ),
        Source(
            "recherche",
            "Workflow Definition, deterministic constraints",
            "https://docs.temporal.io/workflow-definition",
        ),
        Source(
            "recherche",
            "Python SDK sandbox",
            "https://docs.temporal.io/develop/python/python-sdk-sandbox",
        ),
        Source(
            "recherche",
            "Annonces Replay 2026",
            "https://temporal.io/blog/replay-2026-product-announcements",
        ),
        Source("execute", "temporalio 1.33.0, introspection des decorateurs defn"),
    ],
)
