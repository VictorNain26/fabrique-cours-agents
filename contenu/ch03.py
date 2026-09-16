from __future__ import annotations

from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 3. Gestion du contexte
# ═════════════════════════════════════════════════════════════════════════ #

SQ3 = """
# Atelier 3 — compaction de contexte.
from __future__ import annotations

from typing import Callable, TypedDict


class Message(TypedDict):
    role: str
    contenu: str
    tokens: int


def estimer(texte: str) -> int:
    return max(1, len(texte) // 4)


def compacter(
    messages: list[dict],
    budget: int,
    resumer: Callable[[list[dict]], str],
) -> list[dict]:
    # Renvoie une nouvelle liste dont la somme des tokens <= budget.
    #  - tous les messages "system" sont conserves, en tete, dans l'ordre
    #  - on garde ensuite le plus de messages RECENTS possible
    #  - les ecartes passent dans resumer(liste) -> str, insere juste apres les system
    #    sous la forme {"role": "system", "contenu": resume, "tokens": estimer(resume)}
    #  - resumer n'est appele que s'il y a au moins un ecarte
    #  - l'ordre chronologique est preserve
    raise NotImplementedError
"""


def verif3(m):
    f = ok(m, "compacter")
    res, appels = [], {"n": 0}

    def resumer(msgs):
        appels["n"] += 1
        return "R" * 8

    sysm = {"role": "system", "contenu": "regles", "tokens": 10}
    msgs = [sysm] + [{"role": "user", "contenu": f"m{i}", "tokens": 10} for i in range(5)]

    sortie = f(list(msgs), 200, resumer)
    res.append((len(sortie) == 6, "si tout rentre, rien n'est retire"))
    res.append((appels["n"] == 0, "resumer n'est pas appele pour rien"))

    appels["n"] = 0
    s2 = f(list(msgs), 42, resumer)
    total = sum(x["tokens"] for x in s2)
    res.append((total <= 42, f"budget respecte ({total}/42)"))
    res.append((appels["n"] == 1, "resumer appele une seule fois"))
    res.append((any(x["contenu"] == "regles" for x in s2), "le systeme est conserve"))
    res.append((s2[-1]["contenu"] == "m4", "le message le plus recent est la"))
    c = [x["contenu"] for x in s2 if x["contenu"].startswith("m")]
    res.append((c == sorted(c), "ordre chronologique preserve"))
    return res


CH3 = Chapitre(
    numero=3,
    titre="Gestion du contexte",
    objectif="tenir un workflow long sans exploser la fenetre ni la facture",
    duree_min=25,
    blocs=[
        T(
            "La gestion du contexte est ce qui separe un demonstrateur d'un agent qui tient "
            "douze etapes."
        ),
        H("Quatre leviers, dans cet ordre"),
        T(
            "Un. Ne pas faire entrer ce qui ne sert pas : un outil qui renvoie huit mille "
            "tokens de JSON doit filtrer, paginer et resumer de son cote. Deux. Passer par "
            "des references plutot que des valeurs. Trois. Compacter. Quatre. Isoler dans un "
            "sous-agent qui a son propre contexte et ne rend que sa conclusion."
        ),
        A("Cet ordre de priorite est ma position, pas une citation, pas une regle officielle."),
        H("L'outil existe deja dans la stack"),
        T(
            "langchain-core fournit trim_messages, qui fait le travail standard. Signature "
            "reelle verifiee dans le venv du cours : messages, max_tokens, token_counter, "
            "strategy, allow_partial, end_on, start_on, include_system, text_splitter."
        ),
        C("""from langchain_core.messages import trim_messages, SystemMessage, HumanMessage

msgs = [SystemMessage("regles")] + [HumanMessage(f"m{i}") for i in range(5)]
trim_messages(msgs, max_tokens=3, token_counter=len,
              strategy="last", include_system=True, allow_partial=False)
# execute dans le venv -> [SystemMessage:regles, HumanMessage:m3, HumanMessage:m4]"""),
        T(
            "Tu vas reimplementer ce mecanisme a la main dans l'atelier. Pas pour remplacer "
            "la lib, mais parce que ce qui compte c'est la strategie, pas le nom de "
            "la fonction. Et parce que sur une chaine de generation de pages, tes unites ne "
            "sont pas des messages de chat mais des sections, des briefs et des resultats "
            "d'outils : tu ecriras ta propre version."
        ),
        H("Le cache change l'arbitrage"),
        T(
            "Si ton prefixe est stable, le prompt caching le rend beaucoup moins cher. "
            "Consequence contre intuitive : un gros prefixe fige suivi d'un suffixe court et "
            "variable peut couter moins qu'un contexte moyen qui bouge a chaque appel. "
            "Compacter trop tot casse le cache."
        ),
    ],
    questions=[
        Question(
            enonce="Un outil catalogue renvoie 8000 tokens de JSON a chaque appel. "
            "Meilleure correction ?",
            options=[
                "Augmenter la fenetre de contexte",
                "Filtrer et resumer cote outil avant de renvoyer",
                "Demander au modele d'ignorer les champs inutiles",
                "Baisser la temperature",
            ],
            bonne=1,
            explication="Ce qui n'entre pas dans le contexte ne coute rien et ne distrait "
            "personne.",
            source="auteur",
        ),
        Question(
            enonce="Pourquoi un sous-agent aide sur un workflow long ?",
            options=[
                "Il est specialise donc plus precis",
                "Il travaille dans son propre contexte et ne rend que sa conclusion",
                "Il coute moins cher par token",
                "Il peut tourner en parallele",
            ],
            bonne=1,
            explication="L'isolation du contexte est le benefice principal, la "
            "specialisation et le parallelisme sont des bonus.",
            source="auteur",
        ),
    ],
    kata=Kata(
        module="fabrique.generation.contexte",
        consigne="Implemente compacter. Systeme en tete, le plus de recents possible dans "
        "le budget, le reste resume et insere juste apres le systeme.",
        squelette=SQ3,
        verifier=verif3,
        indice="Separe systeme et non systeme, calcule la place restante, remplis en "
        "partant de la fin avec reversed(). Verifie que le resume lui-meme rentre.",
        dependances=[],
    ),
    a_retenir=[
        "Comment tu tiens un workflow a douze etapes sans que le contexte explose.",
        "Pourquoi une fenetre plus grande n'est pas une solution.",
    ],
    sources=[
        Source("execute", "langchain-core 1.6.3, trim_messages signature et sortie"),
        Source(
            "recherche",
            "Context engineering, Anthropic Engineering",
            "https://www.anthropic.com/engineering",
        ),
        Source("auteur", "L'ordre de priorite des quatre leviers"),
    ],
)
