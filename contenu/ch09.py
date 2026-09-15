from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 9. Validation humaine
# ═════════════════════════════════════════════════════════════════════════ #

SQ9 = '''
"""Detection et reprise d'une execution suspendue en attente de validation humaine.

Formes observees sur langgraph 1.2.11, verifiees par execution :
  - invoke() sur un graphe qui s'interrompt renvoie un etat portant la cle
    "__interrupt__", un tuple d'objets Interrupt(value=..., id=...)
  - get_state(config).next donne les noeuds en attente, ex ("validation_humaine",)
  - la reprise passe par invoke(Command(resume=...), config)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from langgraph.types import Command


@dataclass(frozen=True)
class Interruption:
    noeud: str
    charge: Any


def interruption(etat: dict, graphe, config: dict) -> Interruption | None:
    # Renvoie l'interruption en cours, ou None si l'execution est terminee.
    # etat.get("__interrupt__") est un tuple d'objets Interrupt : absent ou
    # vide -> termine, renvoie None.
    # Le noeud en attente vient de graphe.get_state(config).next (un tuple ;
    # prends le premier element, ou "" s'il est vide).
    # La charge utile est le .value du premier element du tuple d'Interrupt.
    raise NotImplementedError


def en_attente(graphe, config: dict) -> bool:
    # Vrai si graphe.get_state(config).next est non vide.
    raise NotImplementedError


def reprendre(graphe, config: dict, *, approuve: bool, commentaire: str = "") -> dict:
    # Rend la main au graphe avec la decision humaine.
    # La valeur passee a resume est EXACTEMENT ce que interrupt() renvoie dans
    # le noeud suspendu (regarde noeud_validation_humaine dans graphe.py) :
    # {"approuve": approuve, "commentaire": commentaire}.
    raise NotImplementedError
'''


def verif9(m):
    from langgraph.checkpoint.memory import InMemorySaver

    from fabrique.generation.graphe import construire
    from fabrique.providers.fake import FournisseurFake

    Interruption = ok(m, "Interruption")
    interruption = ok(m, "interruption")
    en_attente = ok(m, "en_attente")
    reprendre = ok(m, "reprendre")

    pages_existantes = {"/vps"}

    def monter():
        publiees = []
        graphe = construire(
            [FournisseurFake()],
            pages_existantes,
            checkpointer=InMemorySaver(),
            publier=lambda page: publiees.append(page) or "pub-1",
        )
        return graphe, publiees

    res = []

    graphe, _ = monter()
    config = {"configurable": {"thread_id": "k1"}}
    etat = graphe.invoke({"brief": "page vps", "essais": 0}, config=config)

    inter = interruption(etat, graphe, config)
    res.append((inter is not None, "une interruption est detectee sur un graphe suspendu"))
    res.append((isinstance(inter, Interruption), "interruption() rend une Interruption"))
    res.append(
        (
            getattr(inter, "noeud", None) == "validation_humaine",
            "le noeud en attente est validation_humaine",
        ),
    )
    res.append((en_attente(graphe, config) is True, "en_attente() est vrai pendant la suspension"))

    graphe, publiees = monter()
    config = {"configurable": {"thread_id": "k2"}}
    graphe.invoke({"brief": "page vps", "essais": 0}, config=config)

    final = reprendre(graphe, config, approuve=True, commentaire="ok")
    res.append((final.get("publiee") is True, "reprise approuvee -> page publiee"))
    res.append((len(publiees) == 1, "la publication a lieu exactement une fois"))
    res.append(
        (en_attente(graphe, config) is False, "plus en attente une fois la reprise terminee")
    )
    res.append(
        (interruption(final, graphe, config) is None, "interruption() rend None une fois termine")
    )

    graphe, publiees = monter()
    config = {"configurable": {"thread_id": "k3"}}
    graphe.invoke({"brief": "page vps", "essais": 0}, config=config)

    final = reprendre(graphe, config, approuve=False, commentaire="a revoir")
    res.append((not final.get("publiee"), "reprise refusee -> page non publiee"))
    res.append((publiees == [], "reprise refusee -> publier() n'est jamais appele"))

    return res


CH9 = Chapitre(
    numero=9,
    titre="Validation humaine",
    objectif="suspendre une generation, attendre une decision humaine, reprendre sans effet de bord double",
    duree_min=30,
    blocs=[
        T(
            "Une page qui contient encore une violation avertissement, ou qui touche a "
            "quelque chose de sensible, ne part pas seule en production. Ce chapitre "
            "cable ce garde-fou dans le graphe lui-meme, pas a cote."
        ),
        H("Ce que fait interrupt()"),
        T(
            "Verifie par execution sur langgraph 1.2.11 : un noeud qui appelle "
            "interrupt(charge) suspend le graphe. graphe.invoke(etat, config) rend alors "
            'un etat qui porte la cle "__interrupt__", un tuple d\'objets '
            "Interrupt(value=..., id=...). La charge utile que tu as passee a interrupt() "
            "se retrouve dans .value du premier element."
        ),
        C("""etat = graphe.invoke({"brief": "page vps", "essais": 0}, config=config)
etat["__interrupt__"]
# (Interrupt(value={'page': {...}, 'violations': [...]}, id='...'),)"""),
        T(
            "Deux autres lectures possibles sur le meme graphe suspendu, verifiees par "
            "execution : graphe.get_state(config).next donne le tuple des noeuds en "
            'attente, ici ("validation_humaine",). Et graphe.get_state(config).tasks '
            "rend des PregelTask, chacun avec son .interrupts : utile si plusieurs "
            "branches peuvent s'interrompre en parallele, ce qui n'est pas le cas ici."
        ),
        H("La reprise"),
        T(
            "interrupt() exige un checkpointer et un thread_id dans la config : sans eux "
            "il n'y a rien ou stocker l'etat suspendu, et rien a quoi rattacher la "
            "reprise. La reprise elle-meme passe par Command : "
            "graphe.invoke(Command(resume=valeur), config=config). La valeur passee a "
            "resume est EXACTEMENT ce que interrupt() renvoie a l'interieur du noeud, "
            "c'est le contrat entre l'appelant (une route HTTP, chapitre 10) et le graphe."
        ),
        C("""# dans le noeud :
reponse = interrupt({"page": etat["page"], "violations": etat["violations"]})
# reponse == {"approuve": True, "commentaire": "ok"}

# cote appelant, apres la decision humaine :
graphe.invoke(Command(resume={"approuve": True, "commentaire": "ok"}), config=config)"""),
        H("La regle qui casse tout si on l'ignore"),
        A(
            "Source doc, https://docs.langchain.com/oss/python/langgraph/interrupts : un "
            "noeud contenant interrupt() est REJOUE DEPUIS LE DEBUT a chaque reprise. "
            "Tout ce qui precede l'appel a interrupt() a l'interieur de la fonction "
            "s'execute une seconde fois."
        ),
        T(
            "Consequence directe : un effet de bord place avant interrupt() dans le meme "
            "noeud se produit deux fois, une fois pendant la suspension initiale et une "
            "fois au reveil. La parade tient en deux regles. Un : l'effet de bord vit dans "
            "un noeud separe, execute seulement apres l'approbation, jamais dans le noeud "
            "qui contient interrupt(). Deux : toute ecriture qui doit rester avant un "
            "interrupt() est un upsert, jamais un insert nu, au cas ou une reprise "
            "inattendue la rejoue quand meme."
        ),
        H("Le cas metier : la page publiee deux fois"),
        T(
            "Imagine que noeud_validation_humaine appelle publier(page) juste avant "
            'interrupt(), pour "prevenir tout de suite que la page est prete". '
            "L'accusé de reception HTTP se perd, le client retente l'appel : le noeud est "
            "rejoue depuis le debut, publier(page) tourne une seconde fois. Deux pages "
            "identiques en ligne, deux entrees dans le CMS, deux factures si publier() "
            "declenche un webhook facture. Rien n'a plante, et pourtant tout est faux."
        ),
        T(
            "Le graphe de la fabrique separe deja les deux : noeud_validation_humaine ne "
            "fait qu'appeler interrupt() et lire la reponse, noeud_publication est un "
            "noeud a part qui tourne seulement apres, sur la branche approuve du routeur. "
            "Rejouer noeud_validation_humaine ne republie jamais rien, parce que la "
            "publication n'y habite pas."
        ),
        C("""def noeud_validation_humaine(etat: EtatPage) -> dict:
    reponse = interrupt({"page": etat.get("page"), "violations": etat.get("violations", [])})
    return {"approuve": bool(reponse.get("approuve", False)), ...}
    # rien d'autre ici : rejouable sans consequence

def noeud_publication(etat: EtatPage) -> dict:
    identifiant = publier(page)   # l'effet de bord, dans un noeud a part
    return {"publiee": True, ...}"""),
        H("Trois fonctions, un contrat simple"),
        T(
            'interruption(etat, graphe, config) traduit "__interrupt__" et .next en un '
            "objet Interruption(noeud, charge), ou None si tout est termine. "
            'en_attente(graphe, config) repond a la question booleenne "est-ce que '
            "quelqu'un doit encore decider\". reprendre(graphe, config, approuve=, "
            "commentaire=) referme la boucle. Aucune des trois ne touche a de l'IO en "
            "dehors du graphe : elles ne font que lire et ecrire son etat."
        ),
    ],
    questions=[
        Question(
            enonce="A la reprise d'un graphe suspendu, que se passe-t-il pour le noeud "
            "qui contient interrupt() ?",
            options=[
                "Il reprend juste apres l'appel a interrupt()",
                "Il est rejoue depuis le debut de la fonction",
                "Il ne s'execute plus jamais",
                "Seul le reste du graphe redemarre, ce noeud est saute",
            ],
            bonne=1,
            explication="Tout ce qui precede interrupt() dans la fonction s'execute une "
            "seconde fois. C'est documente, et ca change ou placer un effet de bord.",
            source="doc",
        ),
        Question(
            enonce="Pourquoi noeud_publication est-il separe de noeud_validation_humaine ?",
            options=[
                "Pour des raisons de lisibilite uniquement",
                "Parce que le noeud d'interruption est rejoue et publierait deux fois",
                "LangGraph interdit interrupt() et un effet de bord dans le meme graphe",
                "Pour paralleliser les deux noeuds",
            ],
            bonne=1,
            explication="Si publier() vivait dans le noeud qui appelle interrupt(), une "
            "reprise rejouerait la publication depuis le debut du noeud.",
            source="auteur",
        ),
        Question(
            enonce="Que doit exactement contenir la valeur passee a Command(resume=...) ?",
            options=[
                "N'importe quel dict, le graphe l'ignore de toute facon",
                "Exactement ce que interrupt() renvoie dans le noeud suspendu",
                "Le nom du prochain noeud a executer",
                "L'etat complet du graphe",
            ],
            bonne=1,
            explication="C'est le contrat entre l'appelant et le graphe : resume() "
            "devient la valeur de retour de l'appel a interrupt() dans le noeud.",
            source="execute",
        ),
    ],
    kata=Kata(
        module="fabrique.generation.reprise",
        consigne="Implemente Interruption, interruption, en_attente et reprendre. Le "
        "correcteur construit un vrai graphe avec un fournisseur fake et un "
        "checkpointer en memoire, le suspend, et verifie que la reprise publie "
        "exactement une fois quand elle est approuvee, jamais quand elle est refusee.",
        squelette=SQ9,
        verifier=verif9,
        indice="interruption() : brutes = etat.get('__interrupt__') ; si vide, None. "
        "Sinon noeud = graphe.get_state(config).next[0] si non vide sinon ''. "
        "charge = brutes[0].value. en_attente() : bool(graphe.get_state(config).next). "
        "reprendre() : graphe.invoke(Command(resume={'approuve': approuve, "
        "'commentaire': commentaire}), config=config).",
        dependances=["langgraph", "pydantic"],
    ),
    entretien=[
        "Explique pourquoi un noeud avec interrupt() est rejoue depuis le debut, et ce "
        "que ca t'interdit d'y mettre.",
        "Donne un exemple metier ou ignorer cette regle produit un doublon silencieux.",
        "Ou vit exactement l'effet de bord de publication dans le graphe de la fabrique, "
        "et pourquoi la a cet endroit.",
    ],
    sources=[
        Source(
            "doc",
            "LangGraph, interrupt() et reprise avec Command",
            "https://docs.langchain.com/oss/python/langgraph/interrupts",
        ),
        Source(
            "execute",
            'langgraph 1.2.11 : invoke() renvoie "__interrupt__" (tuple d\'Interrupt), '
            "get_state(config).next, get_state(config).tasks[].interrupts, reprise via "
            "invoke(Command(resume=...), config)",
        ),
        Source(
            "auteur",
            "La separation noeud d'interruption / noeud d'effet de bord, et l'exemple de la page publiee deux fois",
        ),
    ],
)
