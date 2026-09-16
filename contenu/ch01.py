from __future__ import annotations

from contenu.commun import A, C, H, T, ok
from modele import Chapitre, Kata, Question, Source

# ═════════════════════════════════════════════════════════════════════════ #
# 1. Pydantic v2 : sortie structurée et boucle de réparation
# ═════════════════════════════════════════════════════════════════════════ #

SQ1 = """
# Atelier 1 — boucle de reparation avec les vraies exceptions Pydantic v2.
from __future__ import annotations

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from fabrique.providers.base import Fournisseur, SortieInvalide

M = TypeVar("M", bound=BaseModel)


def message_de_reparation(e: ValidationError) -> str:
    # Une ligne par erreur, "chemin.du.champ: message". C'est ce texte qui
    # repart vers le fournisseur pour qu'il se corrige : il doit nommer le
    # champ fautif, pas seulement dire "invalide".
    raise NotImplementedError


def generer_valide(
    fournisseur: Fournisseur,
    *,
    invite: str,
    schema: type[M],
    systeme: str = "",
    max_essais: int = 2,
) -> M:
    # Boucle bornee a max_essais. `retour` vaut None au premier essai puis
    # message_de_reparation(e) apres un echec de validation.
    # fournisseur.generer(invite=..., schema=..., systeme=..., retour=...)
    #   -> Reponse(texte=...) ; schema.model_validate_json(reponse.texte)
    #   leve ValidationError si le JSON ne respecte pas le schema.
    # Renvoie l'instance validee au premier succes.
    # Leve SortieInvalide apres epuisement, avec la derniere ValidationError
    # comme cause (raise ... from ...).
    raise NotImplementedError
"""


def verif1(m):
    generer_valide = ok(m, "generer_valide")
    message_de_reparation = ok(m, "message_de_reparation")

    from pydantic import BaseModel, Field, ValidationError

    from fabrique.providers.base import Reponse, SortieInvalide

    class Sortie(BaseModel):
        titre_h1: str = Field(max_length=70)
        meta_description: str = Field(min_length=120, max_length=158)

    BON = '{"titre_h1": "VPS", "meta_description": "' + "d" * 130 + '"}'
    MAUVAIS = '{"titre_h1": "VPS", "meta_description": "trop court"}'

    class FournisseurDouble:
        def __init__(self, reponses):
            self.nom = "double"
            self.cout_par_appel = 0.01
            self._reponses = list(reponses)
            self.appels = []

        def generer(self, *, invite, schema, systeme="", retour=None):
            self.appels.append(retour)
            return Reponse(texte=self._reponses[len(self.appels) - 1], modele="double")

    res = []

    f1 = FournisseurDouble([BON])
    sortie = generer_valide(f1, invite="genere", schema=Sortie)
    res.append((isinstance(sortie, Sortie), "succes direct : instance validee"))
    res.append((f1.appels == [None], "premier appel sans retour d'erreur"))

    f2 = FournisseurDouble([MAUVAIS, BON])
    sortie2 = generer_valide(f2, invite="genere", schema=Sortie)
    res.append((isinstance(sortie2, Sortie), "reparation au deuxieme essai"))
    res.append(
        (
            len(f2.appels) == 2 and bool(f2.appels[1]) and "meta_description" in f2.appels[1],
            "le retour transmis au deuxieme appel nomme le champ fautif",
        ),
    )

    f3 = FournisseurDouble([MAUVAIS, MAUVAIS, MAUVAIS])
    leve = None
    try:
        generer_valide(f3, invite="genere", schema=Sortie, max_essais=3)
    except Exception as e:
        leve = e
    res.append((isinstance(leve, SortieInvalide), "SortieInvalide apres epuisement"))
    res.append((len(f3.appels) == 3, "boucle bornee : exactement 3 appels"))
    res.append(
        (
            leve is not None and isinstance(leve.__cause__, ValidationError),
            "la ValidationError est conservee comme cause",
        ),
    )

    try:
        Sortie.model_validate_json(MAUVAIS)
        msg = ""
    except ValidationError as e:
        msg = message_de_reparation(e)
    res.append(("meta_description" in msg, "message_de_reparation cite le chemin du champ fautif"))
    return res


CH1 = Chapitre(
    numero=1,
    titre="Pydantic v2 : sortie structurée et réparation",
    objectif="obtenir du JSON exploitable et réparer proprement quand il ne l'est pas",
    duree_min=25,
    blocs=[
        T(
            "Version installee dans le venv du cours : pydantic 2.13.5. C'est la version "
            "de la famille Pydantic v2 utilisee dans tout le cours."
        ),
        H("Le contrat"),
        C("""from typing import Literal
from pydantic import BaseModel, Field

class BlocPage(BaseModel):
    type: Literal["titre", "paragraphe", "cta"]
    contenu: str = Field(max_length=200)

class Page(BaseModel):
    titre_h1: str = Field(max_length=70)
    meta_description: str = Field(min_length=120, max_length=158)
    blocs: list[BlocPage] = Field(min_length=1)"""),
        T(
            "Le Literal est le garde-fou le moins cher du lot : le modele ne peut plus "
            "inventer un type de bloc que ton front ne sait pas afficher. Chaque contrainte "
            "ici est une erreur que tu n'auras pas a detecter plus loin dans la chaine."
        ),
        H("L'erreur est une donnee, pas un message"),
        T(
            "ValidationError.errors() renvoie une liste de dictionnaires avec loc, msg et "
            "type. C'est structure, donc exploitable par ton code comme par le modele."
        ),
        C("""try:
    page = Page.model_validate_json(brut)
except ValidationError as e:
    for err in e.errors():
        print(err["loc"], err["msg"], err["type"])
    # ('meta_description',) String should have at least 120 characters too_short"""),
        T(
            "Sortie ci-dessus verifiee en executant le code dans le venv du cours. C'est "
            "exactement ce que tu renvoies au modele pour qu'il se corrige."
        ),
        H("Cote fournisseur"),
        T(
            "Trois techniques coexistent pour obtenir une structure : parser un bloc JSON "
            "dans du texte libre, detourner le tool calling en declarant un outil dont les "
            "arguments sont ton schema, ou utiliser les sorties structurees natives ou le "
            "fournisseur contraint la generation. Les garanties montent dans cet ordre. "
            "Identifie laquelle tu utilises et pourquoi, pour chaque appel que tu ecris."
        ),
        A(
            "Aucune des trois ne garantit que le contenu est juste. Un JSON parfaitement "
            "valide peut annoncer un prix invente. Forme et sens sont deux problemes "
            "separes, le second est traite au chapitre 5."
        ),
        H("La boucle"),
        T(
            "Relancer le meme appel a l'identique apres un echec de validation ne sert a "
            "rien : le modele ne sait pas ce qui a casse. Tu lui renvoies l'erreur, et tu "
            "bornes. Deux essais, trois au maximum."
        ),
    ],
    questions=[
        Question(
            enonce="Que renvoie ValidationError.errors() en Pydantic v2 ?",
            options=[
                "Une chaine de caracteres formatee",
                "Une liste de dictionnaires avec loc, msg et type",
                "Un dict champ -> message",
                "Une exception par champ fautif",
            ],
            bonne=1,
            explication="Une liste de dicts structures. C'est ce qui permet de router "
            "l'erreur : la renvoyer au modele, ou la transformer en metrique.",
            source="verifie en executant pydantic 2.13.5",
        ),
        Question(
            enonce="Ton schema passe de 8 a 40 champs. Effet le plus probable ?",
            options=[
                "Aucun, le modele suit le schema quelle que soit sa taille",
                "La qualite se degrade, mieux vaut decouper en plusieurs appels",
                "Le cout baisse",
                "La validation devient impossible",
            ],
            bonne=1,
            explication="Position d'auteur, pas une citation : c'est un constat de "
            "praticien largement partage, mais ce n'est pas un chiffre "
            "documente.",
            source="auteur",
        ),
    ],
    kata=Kata(
        module="fabrique.generation.reparation",
        consigne="Ecris la boucle de reparation de la fabrique. Le retour transmis au "
        "fournisseur doit nommer le champ fautif, sinon il ne peut pas se "
        "corriger. Le correcteur verifie ce point precis, ainsi que la cause "
        "conservee sur l'exception finale.",
        squelette=SQ1,
        verifier=verif1,
        indice="for _ in range(max_essais): appelle fournisseur.generer(retour=retour), "
        "essaie schema.model_validate_json(reponse.texte). except ValidationError "
        "as e: retour = message_de_reparation(e). raise SortieInvalide(...) from "
        "derniere_erreur pour garder la cause.",
        dependances=["pydantic"],
    ),
    a_retenir=[
        "Quelle technique de sortie structuree tu utilises et quelles garanties elle donne.",
        "Comment tu bornes une boucle de reparation et ce que tu fais au dernier essai rate.",
    ],
    sources=[
        Source("execute", "pydantic 2.13.5, ValidationError.errors() et model_validate_json"),
        Source("recherche", "Structured outputs, docs Anthropic", "https://docs.claude.com"),
        Source("doc", "Pydantic, documentation officielle", "https://docs.pydantic.dev/latest/"),
    ],
)
