"""Helpers partages par tous les chapitres."""

from modele import Bloc


def T(txt):
    return Bloc("texte", txt)


def C(txt):
    return Bloc("code", txt)


def H(txt):
    return Bloc("titre", txt)


def A(txt):
    return Bloc("alerte", txt)


def ok(module, nom):
    val = getattr(module, nom, None)
    if val is None:
        raise AssertionError(f"il manque `{nom}` dans ton fichier")
    return val
