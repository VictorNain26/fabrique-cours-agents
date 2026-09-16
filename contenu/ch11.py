from __future__ import annotations

from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 11. Observabilite
# ═════════════════════════════════════════════════════════════════════════ #

SQ11 = '''
"""Instrumentation Langfuse de la fabrique.

Sans cles configurees, `get_client()` renvoie un client desactive qui absorbe
tous les appels sans lever : ce module reste donc utilisable en local et en CI
sans compte Langfuse.
"""

from __future__ import annotations

from langfuse import get_client, observe

from fabrique.config import reglages
from fabrique.modeles import Violation

__all__ = ["actif", "observe", "tracer_violation", "vider"]


def actif() -> bool:
    # True seulement si les deux cles publique et secrete sont non vides dans
    # reglages(). Une seule des deux presente ne suffit pas.
    raise NotImplementedError


def tracer_violation(v: Violation) -> None:
    # Si actif() est faux, ne fais rien.
    # Sinon, appelle get_client().create_score(...) avec :
    #   name=v.code (le code sert de nom de metrique, pas le message)
    #   value=1.0, data_type="BOOLEAN"   (create_score n'accepte pas de bool)
    #   comment=v.message
    raise NotImplementedError


def vider() -> None:
    # Un seul appel : get_client().flush()
    raise NotImplementedError
'''


def verif11(m):
    from fabrique.modeles import Violation

    actif = ok(m, "actif")
    tracer_violation = ok(m, "tracer_violation")
    vider = ok(m, "vider")
    observe = ok(m, "observe")
    res = []

    res.append((actif() is False, "actif() renvoie False sans cles Langfuse dans l'environnement"))

    v = Violation(code="PRIX_EN_DUR", gravite="bloquant", message="test", indice="i")
    leve = None
    try:
        tracer_violation(v)
    except Exception as e:
        leve = e
    res.append((leve is None, "tracer_violation ne leve pas quand le client est desactive"))

    leve = None
    try:
        vider()
    except Exception as e:
        leve = e
    res.append((leve is None, "vider ne leve pas"))

    @observe
    def double(x):
        return x * 2

    res.append(
        (
            double(21) == 42,
            "observe est bien reexporte, et decorer une fonction la laisse fonctionner",
        )
    )
    return res


CH11 = Chapitre(
    numero=11,
    titre="Observabilite",
    objectif="voir ce que fait la fabrique en production sans en dependre",
    duree_min=25,
    blocs=[
        T(
            "Le kata precedent t'a donne une porte de qualite avant publication. Celui-ci "
            "te donne les yeux pour voir ce qui se passe apres : combien ca coute, combien "
            "de temps ca prend, et quelles regles se declenchent le plus souvent."
        ),
        H("Quatre imports, une architecture OpenTelemetry"),
        C("""from langfuse import get_client, observe, Evaluation, RegressionError"""),
        T(
            "`get_client` renvoie le client singleton, `observe` est le decorateur de "
            "tracage, `Evaluation` et `RegressionError` servent au chapitre suivant pour la "
            "porte de non-regression. Depuis la version 3, le SDK Python de Langfuse est "
            "batu sur OpenTelemetry : la parente des spans vient de la propagation de "
            "contexte ambiante, pas d'un parametre `parent=` passe a la main."
        ),
        C("""@observe(as_type="tool")
def resoudre_prix(reference: str) -> float:
    ...

@observe(as_type="agent")
def generer_page(brief: str) -> Page:
    return resoudre_prix(...)   # apparait comme un enfant de generer_page"""),
        A(
            "Verifie par introspection sur langfuse 4.15.3 : `observe(func=None, *, "
            "name=None, as_type=None, capture_input=None, capture_output=None, "
            "transform_to_string=None)`. `as_type` accepte 'span', 'generation', 'tool', "
            "'agent', 'chain', 'retriever', 'embedding', 'evaluator' ou 'guardrail'. Pour "
            "structurer sans decorer chaque fonction, deux autres outils existent : "
            "`client.start_as_current_observation(as_type=..., name=...)` en gestionnaire "
            "de contexte pour englober un bloc de code, et `propagate_attributes"
            "(user_id=..., session_id=..., tags=...)` pour attacher des attributs a tout un "
            "sous-arbre d'un coup."
        ),
        H("Le score n'est pas un booleen"),
        C("""get_client().create_score(
    name=v.code,          # "PRIX_EN_DUR", pas le message : c'est ce qu'on va suivre
    value=1.0,
    data_type="BOOLEAN",
    comment=v.message,
)"""),
        T(
            "`create_score` accepte une valeur en float ou en str, mais pas de bool : d'ou "
            '`value=1.0` avec `data_type="BOOLEAN"`, verifie par introspection de la '
            "signature. Le code de la violation sert de nom de score, pas le message : "
            "c'est ce qui permet, six mois plus tard, de tracer un taux de PRIX_EN_DUR dans "
            "le temps au lieu de relire des messages d'erreur un par un."
        ),
        H("Jamais une dependance dure"),
        T(
            "Sans cles configurees, `get_client()` journalise un avertissement "
            "d'authentification et se desactive : `observe` devient un no-op transparent, "
            "`create_score` et `flush` ne font rien et ne levent rien. Verifie en executant "
            "le module sans LANGFUSE_PUBLIC_KEY ni LANGFUSE_SECRET_KEY dans l'environnement. "
            "L'instrumentation ne doit jamais faire tomber la fabrique si Langfuse est en "
            "panne, mal configure, ou simplement absent en local."
        ),
        H("Les six metriques d'une revue hebdomadaire"),
        C("""cout par page                        combien coute une page publiee, tout compris
latence p50 / p95 par etape           quelle etape ralentit, pas juste la moyenne globale
taux de reparation                    part des pages qui ont eu besoin d'un essai de plus
taux d'echec definitif                part des briefs jamais transformes en page publiable
taux de violation par regle           quel garde-fou se declenche le plus, et sur quoi
repartition des categories d'erreur   panne fournisseur, sortie invalide, budget depasse..."""),
        A(
            "Cette liste de six metriques est ma position d'auteur, pas une recommandation "
            "Langfuse. Elle vient de l'usage : ce sont les chiffres qui, une fois par "
            "semaine, disent si la fabrique va bien ou si un prompt recemment change a "
            "degrade quelque chose en silence."
        ),
    ],
    questions=[
        Question(
            enonce="Comment un `observe` imbrique dans un autre `observe` devient-il son "
            "enfant dans la trace ?",
            options=[
                "Il faut lui passer parent=nom_de_la_trace",
                "Par propagation de contexte OpenTelemetry, sans parametre explicite",
                "En appelant client.attach_parent() avant l'appel",
                "Ce n'est possible qu'avec start_as_current_observation",
            ],
            bonne=1,
            explication="Le SDK v3+ est batu sur OpenTelemetry : la parente suit le "
            "contexte d'execution ambiant.",
            source="execute",
        ),
        Question(
            enonce="Comment enregistrer un score booleen avec create_score ?",
            options=[
                "value=True",
                'value=1.0, data_type="BOOLEAN"',
                'value="true"',
                'data_type="BOOLEAN" suffit, value est optionnel',
            ],
            bonne=1,
            explication="create_score accepte value en float ou str mais pas en bool : "
            "d'ou la conversion en 1.0 avec data_type explicite.",
            source="execute",
        ),
        Question(
            enonce="La fabrique tourne sans LANGFUSE_PUBLIC_KEY. Que se passe-t-il en "
            "appelant une fonction decoree @observe ?",
            options=[
                "Une exception au premier appel",
                "La fonction s'execute normalement, rien n'est trace",
                "Le programme refuse de demarrer",
                "Un score d'echec est envoye a Langfuse",
            ],
            bonne=1,
            explication="Client desactive : observe devient un no-op, la fonction tourne "
            "comme si le decorateur n'existait pas.",
            source="execute",
        ),
    ],
    kata=Kata(
        module="fabrique.observabilite",
        consigne="Ecris le module d'observabilite de la fabrique : actif(), "
        "tracer_violation(), vider(), et la reexportation de observe. Le "
        "correcteur tourne sans cles Langfuse : ton module doit rester "
        "silencieux et ne jamais lever dans ce cas.",
        squelette=SQ11,
        verifier=verif11,
        indice="actif() renvoie bool(parametres.langfuse_public_key and "
        "parametres.langfuse_secret_key). tracer_violation fait un early return "
        "si not actif(), sinon get_client().create_score(name=v.code, value=1.0, "
        'data_type="BOOLEAN", comment=v.message). vider() ne fait que '
        "get_client().flush().",
        dependances=["langfuse"],
    ),
    a_retenir=[
        "Pourquoi observe ne doit jamais faire echouer la fabrique quand Langfuse est "
        "indisponible.",
        "Pourquoi le code de violation sert de nom de score, plutot que le message.",
        "Trois des six metriques d'une revue hebdomadaire et ce que chacune detecterait "
        "qu'une autre ne detecte pas.",
    ],
    sources=[
        Source(
            "execute",
            "Signature de observe(), Evaluation et RegressionError "
            "introspectees sur langfuse 4.15.3 installe dans le venv du cours",
        ),
        Source(
            "execute",
            "Comportement sans cles : get_client() journalise "
            "l'avertissement d'authentification et se desactive, observe() devient "
            "un no-op, verifie en executant fabrique.observabilite",
        ),
        Source("auteur", "Les six metriques d'une revue hebdomadaire"),
        Source("auteur", "Le principe : l'instrumentation n'est jamais une dependance dure"),
    ],
)
