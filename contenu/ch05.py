from __future__ import annotations

from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 5. Garde-fous deterministes
# ═════════════════════════════════════════════════════════════════════════ #

SQ5 = '''
"""Garde-fous deterministes appliques a une Page avant publication.

Aucun appel LLM ici : chaque regle est une fonction pure sur des donnees deja
validees par les modeles Pydantic de `fabrique.modeles`.
"""

from __future__ import annotations

import re

from fabrique.modeles import Page, Violation

MOTIF_PRIX = re.compile(r"A_ECRIRE")


def valider(page: Page, pages_existantes: set[str]) -> list[Violation]:
    # Codes attendus, un cas fautif = une Violation :
    #   H1_MULTIPLE            bloquant       s'il n'y a pas exactement un bloc "titre"
    #   PRIX_EN_DUR            bloquant       si bloc.contenu contient un montant en euros
    #   REF_PRODUIT_MANQUANTE  bloquant       bloc "tableau_prix" sans product_ref
    #   LIEN_MORT              avertissement  lien absent de pages_existantes
    #
    # Chaque Violation porte un `indice` actionnable : c'est lui qui repart vers
    # l'agent pour qu'il se corrige. Une violation sans indice ne sert a rien.
    #
    # Le motif de prix doit attraper "4,99 €", "12 EUR", "3.50€", "9 euros",
    # et surtout PAS "4 vCores" ni "2024".
    raise NotImplementedError


def bloquantes(violations: list[Violation]) -> list[Violation]:
    raise NotImplementedError
'''


def verif5(m):
    from fabrique.modeles import BlocPage, Page

    valider = ok(m, "valider")
    bloquantes = ok(m, "bloquantes")
    res = []
    ex = {"/vps", "/stockage"}

    def page(blocs, liens=()):
        return Page(
            titre_h1="VPS",
            meta_description="d" * 130,
            blocs=[BlocPage(**b) for b in blocs],
            liens=list(liens),
        )

    propre = page([{"type": "titre", "contenu": "VPS"}], ["/vps"])
    res.append((valider(propre, ex) == [], "une page propre ne leve rien"))

    ko = page(
        [
            {"type": "titre", "contenu": "A"},
            {"type": "titre", "contenu": "B"},
            {"type": "paragraphe", "contenu": "A partir de 4,99 € par mois"},
            {"type": "tableau_prix", "contenu": "nos offres"},
        ],
        ["/vps", "/inconnu"],
    )
    codes = sorted(v.code for v in valider(ko, ex))
    for c in ("H1_MULTIPLE", "PRIX_EN_DUR", "REF_PRODUIT_MANQUANTE", "LIEN_MORT"):
        res.append((c in codes, f"{c} detecte"))

    v_ko = valider(ko, ex)
    res.append(
        (
            all(x.gravite == "avertissement" for x in v_ko if x.code == "LIEN_MORT"),
            "LIEN_MORT est un avertissement, pas un bloquant",
        ),
    )
    res.append(
        (all(x.indice for x in v_ko), "chaque violation porte un indice actionnable"),
    )
    res.append(
        (len(bloquantes(v_ko)) == len(v_ko) - 1, "bloquantes() ecarte l'avertissement"),
    )

    prix = page(
        [
            {"type": "titre", "contenu": "X"},
            {"type": "paragraphe", "contenu": "12 EUR"},
            {"type": "paragraphe", "contenu": "3.50€"},
            {"type": "paragraphe", "contenu": "a partir de 9 euros"},
        ]
    )
    n = sum(1 for x in valider(prix, ex) if x.code == "PRIX_EN_DUR")
    res.append((n == 3, f"les trois ecritures du prix sont attrapees ({n}/3)"))

    faux = page(
        [
            {"type": "titre", "contenu": "X"},
            {"type": "paragraphe", "contenu": "4 vCores et 8 Go de RAM, depuis 2024"},
        ]
    )
    res.append(
        (
            not [x for x in valider(faux, ex) if x.code == "PRIX_EN_DUR"],
            "pas de faux positif sur '4 vCores' ni '2024'",
        ),
    )
    return res


CH5 = Chapitre(
    numero=5,
    titre="Garde-fous deterministes",
    objectif="transformer un comportement incertain en regles et en tests",
    duree_min=25,
    blocs=[
        T(
            "Transformer un comportement incertain en regles, tests et metriques : c'est "
            "l'objet de ce chapitre."
        ),
        A(
            "Tout ce chapitre est de l'artisanat, pas de la doc. Il n'y a pas de "
            "specification officielle du bon garde-fou. C'est une methode, pas une norme."
        ),
        H("La grille de decision"),
        C("""Le controle est...                        Alors
─────────────────────────────────────────────────────────────
deterministe et verifiable                du code, jamais un LLM
verifiable contre une source de verite    un outil + une assertion
subjectif avec un attendu connu           golden dataset + evaluateur
subjectif sans attendu                    LLM-as-judge, avec ses limites"""),
        T(
            "L'essentiel de la fiabilite vient de la premiere ligne. Repondre j'ajoute un "
            "agent critique a chaque probleme coute du temps, de l'argent et ajoute une "
            "source d'erreur pour un controle qu'une expression reguliere fait sans faute."
        ),
        H("La violation est un objet"),
        C("""Violation(
    code="PRIX_EN_DUR",              # sert de metrique, suivie dans le temps
    gravite="bloquant",              # decide si on publie ou si on alerte
    message="bloc 3 contient 4,99 EUR",
    indice="emets un product_ref",   # renvoye a l'agent, chapitre 1
)"""),
        T(
            "Le code stable est ce qui te permet de dire, six semaines plus tard, que le taux "
            "de PRIX_EN_DUR a triple depuis le changement de prompt. Sans lui tu n'as que des "
            "messages d'erreur."
        ),
        A(
            "Ecris le validateur avant le prompt. Tu decouvriras en l'ecrivant la moitie des "
            "regles implicites que personne ne t'a dites, et tu auras des questions precises "
            "a poser au SEO et a la marque."
        ),
    ],
    questions=[
        Question(
            enonce="L'agent met parfois deux h1. Premiere correction ?",
            options=[
                "Preciser la regle dans le prompt",
                "Un validateur qui rejette, avec renvoi de l'erreur a l'agent",
                "Un agent relecteur de structure",
                "Fine-tuner un modele",
            ],
            bonne=1,
            explication="Compter des h1 est deterministe. Le prompt aide sans garantir.",
            source="auteur",
        ),
    ],
    kata=Kata(
        module="fabrique.garde_fous.validateur",
        consigne="Ecris le validateur de la fabrique. Ce n'est pas un exercice : "
        "pendant cet atelier, ton fichier REMPLACE le module de l'app, et "
        "c'est ce chemin-la que le correcteur teste. Le motif de prix doit "
        "attraper les trois ecritures que le modele produit, sans mordre sur "
        "'4 vCores'. Et chaque violation doit porter un indice : c'est lui "
        "qui repart vers l'agent.",
        squelette=SQ5,
        verifier=verif5,
        indice=r'MOTIF_PRIX = re.compile(r"\d+(?:[.,]\d+)?\s*(?:€|eur\b|euros?\b)", '
        r"re.IGNORECASE). Le \b apres eur empeche 'Europe' de matcher, et "
        r"l'absence de separateur tolere entre le nombre et l'unite ecarte "
        r"'4 vCores'.",
        dependances=["pydantic"],
    ),
    a_retenir=[
        "La grille regle / outil / dataset / juge, et quand utiliser laquelle.",
        "Pourquoi le validateur s'ecrit avant le prompt.",
    ],
    sources=[
        Source("auteur", "La grille de decision et le format de Violation"),
        Source(
            "recherche",
            "Building effective agents, Anthropic",
            "https://www.anthropic.com/engineering/building-effective-agents",
        ),
    ],
)
