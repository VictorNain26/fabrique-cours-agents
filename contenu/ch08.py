from __future__ import annotations

from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 8. Erreurs, retry, fallback, couts
# ═════════════════════════════════════════════════════════════════════════ #

SQ8 = """
# Atelier 8 — politique de repli entre fournisseurs, sous enveloppe budgetaire.
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

from fabrique.providers.base import (
    BudgetDepasse,
    Fatale,
    Fournisseur,
    SortieInvalide,
    Surcharge,
)

T = TypeVar("T")


@dataclass(frozen=True)
class Resultat:
    valeur: T
    fournisseur: str
    cout: float
    essais: int


def executer(
    fournisseurs: list[Fournisseur],
    budget: float,
    appel: Callable[[Fournisseur], T],
) -> Resultat[T]:
    # Essaie chaque fournisseur dans l'ordre. Pour chacun :
    #  - fournisseur.cout_par_appel est debite AVANT l'essai ; si le budget
    #    restant ne suffit pas -> BudgetDepasse
    #  - Surcharge      -> abandonne ce fournisseur, passe au suivant, sans
    #                      second essai
    #  - SortieInvalide -> reessaie LE MEME fournisseur une seule fois puis
    #                      abandonne
    #  - Fatale         -> propage immediatement, aucun repli
    #  - succes         -> Resultat(valeur, fournisseur.nom, cout cumule,
    #                      nombre d'essais)
    #  - tous les fournisseurs epuises -> leve Surcharge
    raise NotImplementedError
"""


def verif8(m):
    executer = ok(m, "executer")
    Resultat = ok(m, "Resultat")

    from fabrique.providers.base import BudgetDepasse, Fatale, SortieInvalide, Surcharge

    class FournisseurDouble:
        def __init__(self, nom, cout):
            self.nom = nom
            self.cout_par_appel = cout

    res = []

    a = FournisseurDouble("a", 0.1)
    appels = []

    def bon(f):
        appels.append(f.nom)
        return "page"

    r = executer([a], 1.0, bon)
    res.append((isinstance(r, Resultat), "renvoie un Resultat"))
    res.append(((r.valeur, r.fournisseur) == ("page", "a"), "cas nominal"))
    res.append((abs(r.cout - 0.1) < 1e-9, "le cout de l'essai est compte"))
    res.append((r.essais == 1, "un seul essai au cas nominal"))

    b = FournisseurDouble("b", 5.0)
    vus = []

    def jamais_appele(f):
        vus.append(f.nom)
        return "page"

    leve = None
    try:
        executer([b], 1.0, jamais_appele)
    except Exception as e:
        leve = e
    res.append((isinstance(leve, BudgetDepasse), "BudgetDepasse si le budget ne suffit pas"))
    res.append((vus == [], "budget verifie AVANT l'appel : aucun appel effectue"))

    c1, c2 = FournisseurDouble("c1", 0.1), FournisseurDouble("c2", 0.1)
    compte = {"c1": 0, "c2": 0}

    def surcharge_puis_bon(f):
        compte[f.nom] += 1
        if f.nom == "c1":
            raise Surcharge()
        return "page"

    r = executer([c1, c2], 1.0, surcharge_puis_bon)
    res.append((r.fournisseur == "c2", "Surcharge : bascule vers le fournisseur suivant"))
    res.append((compte["c1"] == 1, "pas de second essai sur un fournisseur surcharge"))

    d = FournisseurDouble("d", 0.1)
    n = {"i": 0}

    def invalide_puis_bon(f):
        n["i"] += 1
        if n["i"] == 1:
            raise SortieInvalide()
        return "page"

    r = executer([d], 1.0, invalide_puis_bon)
    res.append(
        (
            n["i"] == 2 and r.fournisseur == "d",
            "sortie invalide : un seul re-essai du meme fournisseur",
        ),
    )

    e1, e2 = FournisseurDouble("e1", 0.1), FournisseurDouble("e2", 0.1)
    n2 = {"e1": 0, "e2": 0}

    def invalide_persistante(f):
        n2[f.nom] += 1
        if f.nom == "e1":
            raise SortieInvalide()
        return "page"

    r = executer([e1, e2], 1.0, invalide_persistante)
    res.append((n2["e1"] == 2, "sortie invalide : exactement deux essais avant d'abandonner"))
    res.append((r.fournisseur == "e2", "apres epuisement des essais, passe au suivant"))

    f1, f2 = FournisseurDouble("f1", 0.1), FournisseurDouble("f2", 0.1)
    vu_f2 = []

    def fatale(f):
        if f.nom == "f2":
            vu_f2.append(True)
        raise Fatale("cle invalide")

    leve = None
    try:
        executer([f1, f2], 1.0, fatale)
    except Exception as e:
        leve = e
    res.append((isinstance(leve, Fatale), "une Fatale arrete tout, sans repli"))
    res.append((vu_f2 == [], "le fournisseur suivant n'est jamais tente apres une Fatale"))

    g1, g2 = FournisseurDouble("g1", 0.1), FournisseurDouble("g2", 0.1)

    def toujours_surcharge(f):
        raise Surcharge()

    leve = None
    try:
        executer([g1, g2], 1.0, toujours_surcharge)
    except Exception as e:
        leve = e
    res.append((isinstance(leve, Surcharge), "Surcharge quand tous les fournisseurs sont epuises"))

    return res


CH8 = Chapitre(
    numero=8,
    titre="Erreurs, retry, fallback et couts",
    objectif="une categorie d'erreur, une strategie",
    duree_min=25,
    blocs=[
        T(
            "La question n'est pas si un appel va echouer, mais lequel. Le reflexe a "
            "desapprendre est le retry generique avec backoff sur tout : c'est comme ca "
            "qu'une cle invalide devient une facture."
        ),
        H("Quatre categories, quatre strategies"),
        C("""Surcharge / 429       backoff exponentiel, puis repli sur un autre fournisseur
Sortie invalide       un seul re-essai, avec l'erreur renvoyee au modele
Timeout               re-essai si l'appel est idempotent, sinon echec
Fatale (cle, refus)   aucun re-essai, alerte immediate"""),
        A(
            "Cette taxonomie est la mienne. Elle n'est pas tiree d'une doc, elle vient du "
            "recoupement des codes d'erreur des fournisseurs. C'est une grille de praticien, "
            "pas une norme."
        ),
        H("Ce que la plateforme fait deja pour toi"),
        T(
            "Si tes appels LLM sont des activities Temporal, la politique de retry est "
            "declarative : RetryPolicy avec initial_interval, backoff_coefficient et "
            "maximum_attempts, plus les timeouts d'activity. La doc est explicite : les "
            "activities s'executent hors du chemin de rejeu et sont retentees "
            "automatiquement, ce qui evite les erreurs de non-determinisme."
        ),
        T(
            "Consequence pratique : ne reecris pas un backoff maison a l'interieur d'une "
            "activity. Configure la RetryPolicy et laisse la plateforme faire. Ce que tu "
            "gardes en propre, c'est le choix du fournisseur de repli et la borne de "
            "reparation, qui sont des decisions metier."
        ),
        H("Ou vit ce code dans la fabrique"),
        T(
            "Ce n'est pas un exercice isole : le noeud de redaction du graphe appelle "
            "executer(). La chaine de fournisseurs vient de la configuration, ordonnee du "
            "moins cher au plus cher. Par defaut elle ne contient que le fournisseur "
            "factice, pour que ni les tests ni la CI ne depensent d'argent."
        ),
        C(
            """FOURNISSEURS=ovhcloud,anthropic   # OVHcloud d'abord, Anthropic en secours
BUDGET_PAR_PAGE=0.50              # depasse -> l'API renvoie 402"""
        ),
        T(
            "Le graphe garde malgre tout un retry_policy, reduit a la seule Surcharge et a "
            "deux tentatives. Les deux niveaux ne font pas doublon : executer() gere la "
            "politique PAR FOURNISSEUR, le retry du graphe couvre le cas ou la chaine "
            "ENTIERE etait saturee au meme instant."
        ),
        H("Le repli change tes mesures"),
        A(
            "Un repli silencieux vers un autre modele modifie la qualite sans que personne ne "
            "le sache. Le nom du modele qui a reellement repondu doit etre trace et present "
            "dans tes metriques, sinon tes evaluations du chapitre 7 comparent deux choses "
            "differentes sans le voir."
        ),
        H("Les six metriques"),
        T(
            "Cout par page et par agent, latence p50 et p95 par etape, taux de reparation, "
            "taux d'echec definitif, taux de violation par regle, repartition des categories "
            "d'erreur. Ces six la suffisent a tenir une revue hebdomadaire avec un PO."
        ),
    ],
    questions=[
        Question(
            enonce="Tes appels LLM sont des activities Temporal. Ou configures-tu le retry ?",
            options=[
                "Une boucle while avec time.sleep dans l'activity",
                "Une RetryPolicy declarative sur l'activity",
                "Dans le workflow, avec workflow.sleep",
                "Nulle part, Temporal ne retente pas",
            ],
            bonne=1,
            explication="RetryPolicy avec initial_interval, backoff_coefficient et "
            "maximum_attempts. Les activities sont retentees automatiquement.",
            source="doc Temporal, activities et retry",
        ),
        Question(
            enonce="Pourquoi tracer le modele qui a reellement repondu ?",
            options=[
                "Pour la facturation seulement",
                "Parce qu'un repli silencieux fausse toutes tes evaluations",
                "Inutile si le repli marche",
                "Pour le RGPD",
            ],
            bonne=1,
            explication="Si un repli s'est declenche pendant une experience, tu compares "
            "deux prompts avec deux modeles et tu tires la mauvaise conclusion.",
            source="auteur",
        ),
    ],
    kata=Kata(
        module="fabrique.providers.repli",
        consigne="Implemente executer, la politique de repli de la fabrique : chaque "
        "categorie d'erreur a sa strategie, et le budget est verifie avant "
        "chaque essai, pas apres.",
        squelette=SQ8,
        verifier=verif8,
        indice="Boucle sur les fournisseurs, boucle interne de deux essais avec un "
        "drapeau reessai_disponible. break pour passer au suivant, raise pour "
        "Fatale. Debite fournisseur.cout_par_appel avant l'appel.",
        dependances=["pydantic"],
    ),
    a_retenir=[
        "Les categories d'erreur et la strategie de chacune.",
        "Ce qui revient a Temporal et ce qui reste en propre.",
        "Les six metriques d'un tableau de bord de suivi.",
    ],
    sources=[
        Source(
            "recherche",
            "Temporal, activities et retry automatique",
            "https://docs.temporal.io/workflow-definition",
        ),
        Source("execute", "temporalio 1.33.0, RetryPolicy depuis temporalio.common"),
        Source("auteur", "La taxonomie en quatre categories et les six metriques"),
    ],
)
