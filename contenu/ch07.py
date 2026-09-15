from __future__ import annotations

from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 7. Evaluation
# ═════════════════════════════════════════════════════════════════════════ #

SQ7 = '''
"""Harnais d'evaluation : execution locale (CI, sans reseau) et via Langfuse.

Langfuse 4 fait deja la plus grosse partie du travail : run_experiment(), les
evaluateurs code, le calcul des scores par item. Ce qu'il te reste a ecrire :
un harnais local qui tourne sans reseau ni cle pour la CI, et surtout le choix
du dataset et de la marge, qui sont des decisions metier, pas du SDK.
"""

from __future__ import annotations

from collections import defaultdict
from statistics import mean
from typing import Any, Callable

from langfuse import Evaluation, RegressionError
from langfuse.experiment import ExperimentResult

from fabrique.evaluation.dataset import CAS, CasGolden
from fabrique.evaluation.evaluateurs import (
    refs_produit_resolues,
    respecte_longueurs,
    sans_violation_bloquante,
)

Tache = Callable[..., Any]
FonctionEvaluateur = Callable[..., Evaluation | list[Evaluation]]

EVALUATEURS_PAR_DEFAUT: list[FonctionEvaluateur] = [
    sans_violation_bloquante,
    respecte_longueurs,
    refs_produit_resolues,
]


def _item_de(cas: CasGolden) -> dict[str, Any]:
    return {
        "input": cas.brief,
        "expected_output": cas.attendus,
        "metadata": {"identifiant": cas.identifiant, "pages_existantes": sorted(cas.pages_existantes)},
    }


def _evaluations(resultat: Evaluation | list[Evaluation]) -> list[Evaluation]:
    return resultat if isinstance(resultat, list) else [resultat]


def lancer_local(
    task: Tache,
    cas: list[CasGolden] = CAS,
    evaluateurs: list[FonctionEvaluateur] = EVALUATEURS_PAR_DEFAUT,
) -> dict[str, Any]:
    # Pour chaque cas : construis l'item avec _item_de, appelle task(item=item)
    # (task a la signature task(*, item, **kwargs)), puis passe input/output/
    # expected_output/metadata en mots-cles a chaque evaluateur. Un evaluateur
    # peut rendre une Evaluation ou une liste, _evaluations() uniformise.
    # Rends {"moyennes": {nom: moyenne des valeurs numeriques}, "detail": [...]}
    # avec un dict par cas dans detail (identifiant, sortie, evaluations : c'est
    # ce qui te sert a deboguer un echec plus tard).
    raise NotImplementedError


def verdict(baseline: dict[str, Any], candidat: dict[str, Any], marge: float) -> str:
    # baseline et candidat sont les dicts COMPLETS rendus par lancer_local ou
    # lancer_langfuse : lis baseline["moyennes"] et candidat["moyennes"].
    # ValueError si les deux dicts n'ont pas exactement les memes noms de score.
    # Sur chaque score : ecart = candidat - baseline.
    #   au moins un ecart < -marge  -> "regression"
    #   sinon au moins un > +marge  -> "amelioration"
    #   sinon                       -> "indecis"
    raise NotImplementedError


def exiger_non_regression(baseline: dict[str, Any], candidat: dict[str, Any], marge: float) -> None:
    # Ne fait rien si verdict(...) != "regression".
    # Sinon leve RegressionError(result=..., metric=..., value=..., threshold=...).
    # RegressionError exige un ExperimentResult : construis-en un minimal, sans
    # appel reseau (item_results=[] suffit ici). metric = le score dont l'ecart
    # candidat-baseline est le plus negatif.
    raise NotImplementedError
'''


def verif7(m):
    from langfuse import RegressionError

    from fabrique.evaluation.dataset import CasGolden

    lancer_local = ok(m, "lancer_local")
    verdict = ok(m, "verdict")
    exiger_non_regression = ok(m, "exiger_non_regression")

    res = []

    meta = "M" * 130
    page_bonne = {
        "titre_h1": "Un titre correct",
        "meta_description": meta,
        "blocs": [
            {"type": "titre", "contenu": "Un titre correct"},
            {"type": "tableau_prix", "contenu": "Voir nos offres", "product_ref": "ref-1"},
        ],
        "liens": ["/accueil"],
    }
    page_mauvaise = {
        "titre_h1": "Un titre correct",
        "meta_description": meta,
        "blocs": [
            {"type": "titre", "contenu": "Un titre correct"},
            {"type": "titre", "contenu": "Un second titre"},
            {"type": "tableau_prix", "contenu": "Voir nos offres", "product_ref": None},
        ],
        "liens": ["/accueil"],
    }

    cas_local = [
        CasGolden(identifiant="c1", brief="brief 1", pages_existantes={"/accueil"}, attendus={}),
        CasGolden(identifiant="c2", brief="brief 2", pages_existantes={"/accueil"}, attendus={}),
    ]

    def task_bonne(*, item, **kwargs):
        return page_bonne

    def task_mauvaise(*, item, **kwargs):
        return page_mauvaise

    bonne = lancer_local(task_bonne, cas=cas_local)
    res.append(("moyennes" in bonne and "detail" in bonne, "lancer_local rend moyennes et detail"))
    res.append(
        (
            bonne["moyennes"].get("sans_violation_bloquante") == 1.0,
            "task deterministe bonne -> 1.0",
        ),
    )
    res.append((len(bonne["detail"]) == len(cas_local), "un detail par cas du dataset local"))

    mauvaise = lancer_local(task_mauvaise, cas=cas_local)
    res.append(
        (
            mauvaise["moyennes"].get("sans_violation_bloquante") == 0.0,
            "task deterministe mauvaise -> 0.0",
        ),
    )

    base = {"moyennes": {"score": 0.5}}
    cand_up = {"moyennes": {"score": 0.8}}
    cand_down = {"moyennes": {"score": 0.2}}
    cand_stable = {"moyennes": {"score": 0.52}}
    res.append((verdict(base, cand_up, 0.1) == "amelioration", "ecart positif net -> amelioration"))
    res.append((verdict(base, cand_down, 0.1) == "regression", "ecart negatif net -> regression"))
    res.append((verdict(base, cand_stable, 0.1) == "indecis", "sous la marge -> indecis"))

    leve = None
    try:
        verdict({"moyennes": {"a": 1.0}}, {"moyennes": {"b": 1.0}}, 0.1)
    except Exception as e:
        leve = e
    res.append((isinstance(leve, ValueError), "cles de score divergentes -> ValueError"))

    leve = None
    try:
        exiger_non_regression(base, cand_down, 0.1)
    except Exception as e:
        leve = e
    res.append((isinstance(leve, RegressionError), "regression -> RegressionError"))

    leve = None
    try:
        exiger_non_regression(base, cand_up, 0.1)
    except Exception as e:
        leve = e
    res.append((leve is None, "amelioration -> exiger_non_regression ne leve rien"))

    leve = None
    try:
        exiger_non_regression(base, cand_stable, 0.1)
    except Exception as e:
        leve = e
    res.append((leve is None, "indecis -> exiger_non_regression ne leve rien"))

    return res


CH7 = Chapitre(
    numero=7,
    titre="Evaluation et non-regression",
    objectif="prouver qu'une version est meilleure, pas juste differente",
    duree_min=30,
    blocs=[
        T(
            "Axe deux de la mission, ecrit noir sur blanc : une evolution d'agent ne doit pas "
            "simplement avoir l'air meilleure, on doit pouvoir le mesurer. Tu as deja un "
            "dataset golden sur TomIA, donc tu pars avec de l'avance."
        ),
        H("Ce que Langfuse 4 fait deja pour toi"),
        T(
            "Verifie par introspection sur langfuse 4.15.3 installe dans ce venv : "
            "get_client().run_experiment(*, name, data, task, evaluators, run_evaluators, "
            "composite_evaluator, max_concurrency=50, ...) existe et prend en charge tout le "
            "cablage boucle-sur-le-dataset, appelle-la-tache, appelle-les-evaluateurs, agrege. "
            "task doit accepter item en argument nomme."
        ),
        C("""from langfuse import get_client

resultat = get_client().run_experiment(
    name="fabrique-golden-dataset",
    data=[{"input": ..., "expected_output": ..., "metadata": ...}, ...],
    task=ma_tache,              # def ma_tache(*, item, **kwargs): ...
    evaluators=[mon_evaluateur],
)"""),
        T(
            "Evaluation (aussi importable depuis langfuse) est keyword-only : name, value, "
            "comment, metadata, data_type, config_id. value accepte int, float, str ou bool. "
            "RegressionError, meme module, exige un result de type ExperimentResult : tu ne "
            "peux pas la lever sans construire ce resultat, meme minimal."
        ),
        A(
            "Piege verifie par introspection : create_score (celui qui pousse un score sur "
            "une trace en production) n'accepte QUE float ou str pour value, pas bool. Pour "
            'noter un booleen, passe value=1.0, data_type="BOOLEAN" : c\'est data_type qui '
            "porte le sens, pas le type Python."
        ),
        T(
            "observe(as_type=...) accepte, entre autres, 'guardrail' et 'evaluator' en plus "
            "des types de span habituels (generation, embedding, span, agent, tool, chain, "
            "retriever) : de quoi tracer un garde-fou du chapitre 5 ou un juge LLM comme des "
            "spans identifiables, sans les confondre avec un appel de generation."
        ),
        A(
            "Sans cle configuree, le client Langfuse se desactive silencieusement : il ne "
            "leve pas d'exception, le code instrumente tourne quand meme, il n'y a juste plus "
            "de trace envoyee. Verifie par execution dans ce venv : get_client().auth_check() "
            "rend False sans lever, meme sans LANGFUSE_PUBLIC_KEY. Consequence pratique : une "
            "CI sans cle ne casse pas sur l'instrumentation, mais lancer_langfuse n'y envoie "
            "rien d'utile. C'est pour ca que lancer_local existe."
        ),
        T(
            "Message a retenir : ce que beaucoup reecrivent a la main (boucle sur le dataset, "
            "agregation des scores, structure de resultat) est deja dans le SDK. Ce que tu "
            "gardes en propre, c'est le choix du dataset et la marge — les deux points ou une "
            "decision metier s'invite dans un outil generique."
        ),
        H("Le golden dataset"),
        T(
            "Vingt a trente cas choisis, pas tires au hasard : les cas reels qui ont casse, "
            "les cas limites, quelques cas normaux. Pour chacun, note ce qui est verifiable. "
            "Il vit dans le depot, versionne avec le code."
        ),
        H("Trois niveaux d'evaluateurs"),
        T(
            "Deterministes d'abord, tes validateurs du chapitre 5 rejoues comme des scores. "
            "Puis contre source de verite : le prix correspond-il au catalogue. Puis le juge "
            "LLM, seulement pour ce qui reste subjectif, un juge par critere."
        ),
        H("Les limites du juge"),
        C("""biais de position     l'ordre des reponses influence la note
biais de verbosite    la reponse la plus longue est notee plus haut
auto-preference       un modele note mieux sa propre famille
derive                un juge non fige rend deux runs incomparables"""),
        A(
            "Ces quatre biais sont documentes dans la litterature sur l'evaluation par "
            "modele, mais je ne les ai pas reverifies contre un papier precis en preparant ce "
            "cours. Annonce-les comme connus, pas comme cites."
        ),
        T(
            "La parade tient en une phrase : un juge se calibre contre des annotations "
            "humaines sur un echantillon, puis se fige. Tant que tu n'as pas mesure l'accord "
            "juge-humain, tu n'as pas une metrique, tu as une opinion automatisee."
        ),
    ],
    questions=[
        Question(
            enonce="Ton juge donne 4,3 contre 3,9. Que verifies-tu avant de conclure ?",
            options=[
                "Rien, l'ecart est net",
                "Que le juge est fige, l'accord juge-humain, et la variance du dataset",
                "Tu refais le test avec un juge plus puissant",
                "Tu demandes au juge de justifier",
            ],
            bonne=1,
            explication="Un ecart de 0,4 sur vingt cas peut etre du bruit.",
            source="auteur",
        ),
        Question(
            enonce="Tu veux noter un critere booleen avec create_score. Que passes-tu ?",
            options=[
                "value=True",
                'value=1.0, data_type="BOOLEAN"',
                'value="True"',
                "un objet Evaluation directement",
            ],
            bonne=1,
            explication="create_score n'accepte que float ou str pour value, jamais bool. "
            "C'est data_type qui porte le sens booleen.",
            source="execute",
        ),
        Question(
            enonce="La CI tourne sans LANGFUSE_PUBLIC_KEY. Que se passe-t-il ?",
            options=[
                "Le premier appel instrumente leve une exception",
                "Le client se desactive silencieusement, le code tourne, rien n'est trace",
                "run_experiment refuse de demarrer",
                "Une cle de demonstration est utilisee automatiquement",
            ],
            bonne=1,
            explication="auth_check() rend False sans lever. C'est pour ca qu'un harnais "
            "local sans reseau (lancer_local) reste necessaire en CI.",
            source="execute",
        ),
    ],
    kata=Kata(
        module="fabrique.evaluation.experience",
        consigne="Implemente lancer_local, verdict et exiger_non_regression. Langfuse fait "
        "le gros du travail via run_experiment ; ici tu ecris l'equivalent sans reseau "
        "pour la CI, et la logique de marge qui transforme deux dicts de moyennes en un "
        "verdict exploitable.",
        squelette=SQ7,
        verifier=verif7,
        indice="lancer_local : boucle sur cas, task(item=_item_de(un_cas)), passe "
        "input/output/expected_output/metadata a chaque evaluateur, accumule les valeurs "
        "numeriques par nom avec un defaultdict(list), moyenne avec statistics.mean. "
        "verdict : compare les cles avec des set(), calcule les ecarts, teste d'abord la "
        "regression puis l'amelioration. exiger_non_regression : appelle verdict, "
        "construis un ExperimentResult vide (item_results=[]) avant de lever "
        "RegressionError.",
        dependances=["langfuse", "pydantic"],
    ),
    entretien=[
        "Ce que Langfuse 4 fait deja pour toi, et ce que tu ecris quand meme toi-meme.",
        "Comment tu construis un golden dataset sans verite terrain.",
        "Cite trois biais du LLM-as-judge et la parade.",
    ],
    sources=[
        Source(
            "execute",
            "langfuse 4.15.3, signature de run_experiment (Langfuse.run_experiment), "
            "Evaluation, RegressionError, create_score, observe(as_type=...), "
            "auth_check() sans cle",
        ),
        Source("recherche", "Langfuse, depot GitHub et documentation", "https://docs.langfuse.com"),
        Source(
            "recherche",
            "LLM-as-a-Judge, depreciation v4",
            "https://langfuse.com/docs/evaluation/evaluation-methods/llm-as-a-judge",
        ),
        Source("auteur", "La construction du dataset et la hierarchie des evaluateurs"),
    ],
)
