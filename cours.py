#!/usr/bin/env python3
"""
Cours interactif — Agents IA en production.
Chaque atelier ecrit un vrai module de l'application livree avec le cours.

Usage :
    python3 cours.py            menu principal
    python3 cours.py 3          aller directement au chapitre 3
    python3 cours.py --reset    remettre la progression à zéro
    python3 cours.py --restaurer  remettre l'app en etat apres un atelier

Aucune dépendance. Python 3.10+.
"""

from __future__ import annotations

import importlib.util
import json
import os
import random
import sys
import traceback
from pathlib import Path

from contenu import CHAPITRES
from modele import Chapitre, Kata

RACINE = Path(__file__).parent
ATELIER = RACINE / "atelier"
PROGRESSION = RACINE / ".progression.json"

COULEUR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def c(txt: str, code: str) -> str:
    return f"\033[{code}m{txt}\033[0m" if COULEUR else txt


def gras(t: str) -> str:
    return c(t, "1")


def gris(t: str) -> str:
    return c(t, "90")


def vert(t: str) -> str:
    return c(t, "32")


def rouge(t: str) -> str:
    return c(t, "31")


def jaune(t: str) -> str:
    return c(t, "33")


def cyan(t: str) -> str:
    return c(t, "36")


LARGEUR = min(88, os.get_terminal_size().columns if sys.stdout.isatty() else 88)


# --------------------------------------------------------------------------- #
# Progression
# --------------------------------------------------------------------------- #
def charger() -> dict:
    if PROGRESSION.exists():
        try:
            return json.loads(PROGRESSION.read_text())
        except json.JSONDecodeError:
            pass
    return {"lus": [], "quiz": {}, "katas": []}


def sauver(p: dict) -> None:
    PROGRESSION.write_text(json.dumps(p, indent=2))


# --------------------------------------------------------------------------- #
# Affichage
# --------------------------------------------------------------------------- #
def ligne(char: str = "─") -> str:
    return gris(char * LARGEUR)


def paragraphe(txt: str, indent: str = "") -> None:
    """Retour à la ligne propre sans casser les mots."""
    for para in txt.strip().split("\n"):
        if not para.strip():
            print()
            continue
        mots, courante = para.split(), indent
        for mot in mots:
            if len(courante) + len(mot) + 1 > LARGEUR:
                print(courante)
                courante = indent + mot
            else:
                courante = f"{courante} {mot}" if courante.strip() else indent + mot
        if courante.strip():
            print(courante)


def code(txt: str) -> None:
    for ligne in txt.strip("\n").split("\n"):
        rendu = ligne
        if COULEUR:
            rendu = gris(ligne) if ligne.lstrip().startswith("#") else c(ligne, "36")
        print("   " + rendu)


def attendre(msg: str = "Entrée pour continuer") -> None:
    try:
        input(gris(f"\n   [{msg}] "))
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


def demander(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)


# --------------------------------------------------------------------------- #
# Leçon
# --------------------------------------------------------------------------- #
def jouer_lecon(ch: Chapitre) -> None:
    print()
    print(ligne("━"))
    print(gras(f"  Chapitre {ch.numero} — {ch.titre}"))
    print(gris(f"  Objectif : {ch.objectif}"))
    print(gris(f"  Environ {ch.duree_min} minutes"))
    print(ligne("━"))

    for bloc in ch.blocs:
        print()
        if bloc.kind == "titre":
            print(gras("  " + bloc.contenu.upper()))
            print(gris("  " + "·" * len(bloc.contenu)))
        elif bloc.kind == "code":
            code(bloc.contenu)
        elif bloc.kind == "alerte":
            paragraphe(jaune("!  " + bloc.contenu), indent="  ")
        else:
            paragraphe(bloc.contenu, indent="  ")
        if bloc.kind in ("code", "alerte"):
            attendre()


# --------------------------------------------------------------------------- #
# Quiz
# --------------------------------------------------------------------------- #
def jouer_quiz(ch: Chapitre, prog: dict) -> None:
    if not ch.questions:
        return
    print()
    print(ligne())
    print(gras(f"  Quiz — chapitre {ch.numero}"))
    print(ligne())
    bons = 0
    for i, q in enumerate(ch.questions, 1):
        print()
        paragraphe(gras(f"{i}. {q.enonce}"), indent="  ")
        ordre = list(range(len(q.options)))
        random.shuffle(ordre)
        for j, idx in enumerate(ordre):
            paragraphe(f"{chr(97 + j)}) {q.options[idx]}", indent="     ")
        rep = ""
        while rep not in [chr(97 + k) for k in range(len(ordre))]:
            rep = demander(gris("     ta réponse > ")).lower()[:1]
        choisi = ordre[ord(rep) - 97]
        if choisi == q.bonne:
            bons += 1
            print(vert("     correct."))
        else:
            bonne_lettre = chr(97 + ordre.index(q.bonne))
            print(rouge(f"     non. la bonne réponse est {bonne_lettre})."))
        print()
        paragraphe(gris(q.explication), indent="     ")
    total = len(ch.questions)
    print()
    couleur = vert if bons == total else (jaune if bons >= total * 0.6 else rouge)
    print(couleur(f"  Score : {bons}/{total}"))
    prog["quiz"][str(ch.numero)] = f"{bons}/{total}"
    sauver(prog)


# --------------------------------------------------------------------------- #
# Kata
# --------------------------------------------------------------------------- #
SOLUTIONS = RACINE / ".solutions"


def chemin_module(pointe: str) -> Path:
    return RACINE / (pointe.replace(".", "/") + ".py")


def chemin_remise(pointe: str) -> Path:
    return SOLUTIONS / (pointe + ".py")


def ranger_module(kata: Kata) -> None:
    """Met le vrai module de cote et installe le squelette a sa place."""
    reel, remise = chemin_module(kata.module), chemin_remise(kata.module)
    SOLUTIONS.mkdir(exist_ok=True)
    if not remise.exists() and reel.exists():
        remise.write_text(reel.read_text())
    reel.parent.mkdir(parents=True, exist_ok=True)
    reel.write_text(kata.squelette.lstrip("\n"))


def restaurer_module(kata: Kata) -> bool:
    reel, remise = chemin_module(kata.module), chemin_remise(kata.module)
    if not remise.exists():
        return False
    reel.write_text(remise.read_text())
    remise.unlink()
    return True


def restaurer_tout() -> int:
    from contenu import CHAPITRES as TOUS

    n = 0
    for ch in TOUS:
        if ch.kata and ch.kata.module and restaurer_module(ch.kata):
            n += 1
    return n


def charger_module(chemin: Path):
    spec = importlib.util.spec_from_file_location(f"kata_{chemin.stem}", chemin)
    if spec is None or spec.loader is None:
        raise ImportError(f"impossible de charger {chemin}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def charger_pointe(pointe: str):
    """Recharge le vrai module de l'app, avec ses imports de package intacts."""
    importlib.invalidate_caches()
    for nom in [n for n in sys.modules if n == pointe or n.startswith(pointe + ".")]:
        del sys.modules[nom]
    return importlib.import_module(pointe)


def jouer_kata(ch: Chapitre, prog: dict) -> None:
    kata: Kata | None = ch.kata
    if kata is None:
        return
    manquantes = [d for d in kata.dependances if importlib.util.find_spec(d) is None]
    if manquantes:
        print()
        print(rouge(f"  Cet atelier a besoin de : {', '.join(manquantes)}"))
        print(gris("  installe-les puis reviens :"))
        print(gris(f"     pip install {' '.join(kata.dependances)}"))
        attendre()
        return

    adosse = bool(kata.module)
    if adosse:
        cible = chemin_module(kata.module)
        neuf = not chemin_remise(kata.module).exists()
        if neuf:
            ranger_module(kata)
    else:
        ATELIER.mkdir(exist_ok=True)
        cible = ATELIER / kata.fichier
        neuf = not cible.exists()
        if neuf:
            cible.write_text(kata.squelette.lstrip("\n"))

    print()
    print(ligne())
    print(gras(f"  Atelier — chapitre {ch.numero}"))
    print(ligne())
    print()
    paragraphe(kata.consigne, indent="  ")
    print()
    print(gris(f"  Fichier : {cible.relative_to(RACINE)}"))
    if adosse:
        print(gris("  C'est un vrai module de l'app. Ta version remplace la sienne"))
        print(gris("  le temps de l'atelier, et le correcteur teste ce chemin-la."))
    if neuf:
        print(gris("  (prepare a l'instant, ouvre-le dans ton editeur)"))

    def rendre_la_main():
        if adosse and restaurer_module(kata):
            print(gris("  module de l'app restaure."))

    while True:
        print()
        choix = demander(
            gris("  [v]érifier  [i]ndice  [s]olution  [r]éinitialiser  [q]uitter > ")
        ).lower()[:1]

        if choix == "q":
            rendre_la_main()
            return
        if choix == "i":
            print()
            paragraphe(jaune(kata.indice or "Pas d'indice sur celui-là."), indent="  ")
            continue
        if choix == "r":
            cible.write_text(kata.squelette.lstrip("\n"))
            print(gris("  fichier réinitialisé."))
            continue
        if choix == "s":
            source = kata.solution
            if not source and adosse and chemin_remise(kata.module).exists():
                source = chemin_remise(kata.module).read_text()
            if not source:
                print(gris("  pas de solution fournie."))
                continue
            conf = demander(rouge("  sûr ? tu apprends moins vite. (o/N) > ")).lower()
            if conf == "o":
                print()
                code(source)
            continue
        if choix != "v":
            continue

        print()
        try:
            module = charger_pointe(kata.module) if adosse else charger_module(cible)
        except Exception:
            print(rouge("  ton fichier ne s'exécute pas :"))
            print()
            for ligne in traceback.format_exc().strip().split("\n")[-4:]:
                print(gris("   " + ligne))
            continue

        try:
            resultats = kata.verifier(module)
        except NotImplementedError:
            print(jaune("  pas encore implémenté. ouvre le fichier et enlève le"))
            print(jaune("  raise NotImplementedError, puis reviens ici."))
            continue
        except AssertionError as e:
            print(rouge(f"  {e}"))
            continue
        except Exception:
            print(rouge("  la vérification a planté sur ton code :"))
            print()
            lignes = [
                ligne
                for ligne in traceback.format_exc().strip().split("\n")
                if ligne.strip() and set(ligne.strip()) != {"^"}
            ]
            for ligne in lignes[-4:]:
                print(gris("   " + ligne))
            continue

        for ok, msg in resultats:
            print(("  " + vert("ok   ") if ok else "  " + rouge("échec")) + "  " + msg)

        if all(ok for ok, _ in resultats):
            print()
            print(vert(gras("  Atelier validé.")))
            if ch.numero not in prog["katas"]:
                prog["katas"].append(ch.numero)
                sauver(prog)
            rendre_la_main()
            attendre()
            return


# --------------------------------------------------------------------------- #
# Enchaînement
# --------------------------------------------------------------------------- #
NIVEAUX = {
    "doc": (vert, "doc lue"),
    "recherche": (cyan, "extrait"),
    "execute": (vert, "execute"),
    "auteur": (jaune, "auteur"),
}


def afficher_sources(ch: Chapitre) -> None:
    if not ch.sources:
        return
    print()
    print(ligne())
    print(gras("  Sources"))
    print(gris("  doc lue = page officielle lue en entier · extrait = vu en recherche"))
    print(gris("  execute = verifie en executant le code · auteur = position, pas citation"))
    print(ligne())
    for s in ch.sources:
        couleur, label = NIVEAUX.get(s.niveau, (gris, s.niveau))
        print()
        print("  " + couleur(f"[{label}]") + " " + s.titre)
        if s.url:
            print(gris("     " + s.url))
    print()


def jouer_chapitre(ch: Chapitre, prog: dict) -> None:
    jouer_lecon(ch)
    jouer_quiz(ch, prog)
    jouer_kata(ch, prog)
    afficher_sources(ch)
    if ch.a_retenir:
        print()
        print(ligne())
        print(gras("  Ce que tu dois savoir expliquer"))
        print(ligne())
        for q in ch.a_retenir:
            print()
            paragraphe("• " + q, indent="  ")
        print()
    if ch.numero not in prog["lus"]:
        prog["lus"].append(ch.numero)
        sauver(prog)
    attendre("Entrée pour revenir au menu")


def etat(ch: Chapitre, prog: dict) -> str:
    marques = []
    marques.append(vert("lu") if ch.numero in prog["lus"] else gris("--"))
    q = prog["quiz"].get(str(ch.numero))
    marques.append(cyan(q) if q else gris("---"))
    if ch.kata is None:
        marques.append(gris(" · "))
    else:
        marques.append(vert("kata") if ch.numero in prog["katas"] else rouge("kata"))
    return "  ".join(marques)


def menu() -> None:
    prog = charger()
    while True:
        print()
        print(ligne("━"))
        print(gras("  AGENTS IA EN PRODUCTION — cours interactif"))
        print(gris("  Chaque atelier est un vrai module de l'app. Au bout, un service qui tourne."))
        print(ligne("━"))
        print()
        for ch in CHAPITRES:
            print(f"  {gras(str(ch.numero).rjust(2))}. {ch.titre.ljust(46)}{etat(ch, prog)}")
        print()
        print(gris("  numéro pour ouvrir un chapitre · [e]nv · [r]eset · [q]uitter"))
        choix = demander(gris("  > ")).lower()
        if choix in ("q", "quitter", "exit"):
            print()
            print(gris("  à demain."))
            return
        if choix == "e":
            environnement()
            attendre()
            continue
        if choix == "r":
            if demander(rouge("  tout effacer ? (o/N) > ")).lower() == "o":
                prog = {"lus": [], "quiz": {}, "katas": []}
                sauver(prog)
            continue
        if choix.isdigit():
            n = int(choix)
            ch = next((x for x in CHAPITRES if x.numero == n), None)
            if ch:
                jouer_chapitre(ch, prog)


def environnement() -> None:
    import importlib.metadata as md

    print()
    print(gras("  Environnement"))
    print(ligne())
    print(f"  python {sys.version.split()[0]}")
    for paquet in (
        "pydantic",
        "langgraph",
        "langgraph-checkpoint-postgres",
        "langchain-core",
        "temporalio",
        "mcp",
        "langfuse",
        "openai",
        "fastapi",
    ):
        try:
            v = md.version(paquet)
            print(f"  {vert('ok')}   {paquet.ljust(30)} {v}")
        except Exception:
            print(f"  {rouge('--')}   {paquet.ljust(30)} absent")
    print()
    print(gris("  Versions de reference, relevees par installation reelle le 15/09/2026."))
    print(gris("  Le detail et les sources sont dans docs/verification.md."))
    print()


def main() -> None:
    args = sys.argv[1:]
    if "--env" in args:
        environnement()
        return
    if "--restaurer" in args:
        n = restaurer_tout()
        print(f"{n} module(s) de l'app restaure(s).")
        return
    if "--reset" in args:
        if PROGRESSION.exists():
            PROGRESSION.unlink()
        print("progression effacée.")
        return
    if args and args[0].isdigit():
        prog = charger()
        ch = next((x for x in CHAPITRES if x.numero == int(args[0])), None)
        if ch:
            jouer_chapitre(ch, prog)
            return
    menu()


if __name__ == "__main__":
    main()
