"""Valide un fournisseur reel contre son API. Ne journalise JAMAIS la cle.

    export OVH_API_KEY=...        # ou ANTHROPIC_API_KEY
    python scripts_valider_fournisseur.py ovhcloud

Sort 0 si l'adaptateur produit une Page conforme au schema, 1 sinon.
"""

from __future__ import annotations

import sys

from fabrique.config import reglages
from fabrique.modeles import Page
from fabrique.providers.base import ErreurFournisseur

BRIEF = (
    "Redige une page de vente courte pour une offre de VPS destinee aux "
    "developpeurs. Un seul titre. Pas de prix en dur."
)


def _masque(valeur: str) -> str:
    return f"{valeur[:4]}...{valeur[-2:]} ({len(valeur)} car.)" if valeur else "absente"


def main() -> int:
    nom = sys.argv[1] if len(sys.argv) > 1 else "ovhcloud"

    if nom == "ovhcloud":
        from fabrique.providers.ovhcloud import FournisseurOVHcloud

        cle = reglages().ovh_api_key
        if not cle:
            print("ovh_api_key absente : renseigne OVH_API_KEY dans .env")
            return 1
        print(f"cle OVH_API_KEY : {_masque(cle)}")
        fournisseur = FournisseurOVHcloud(api_key=cle)
    elif nom == "anthropic":
        from fabrique.providers.anthropic import FournisseurAnthropic

        cle = reglages().anthropic_api_key
        if not cle:
            print("anthropic_api_key absente : renseigne ANTHROPIC_API_KEY dans .env")
            return 1
        print(f"cle ANTHROPIC_API_KEY : {_masque(cle)}")
        fournisseur = FournisseurAnthropic(api_key=cle)
    else:
        print(f"fournisseur inconnu : {nom}")
        return 1

    print(f"appel reel de {fournisseur.nom}...")
    try:
        reponse = fournisseur.generer(invite=BRIEF, schema=Page)
    except ErreurFournisseur as e:
        print(f"ECHEC, erreur traduite correctement : {type(e).__name__}: {e}")
        return 1

    print(f"modele ayant repondu : {reponse.modele}")
    print(f"tokens : {reponse.tokens_entree} entree / {reponse.tokens_sortie} sortie")

    try:
        page = Page.model_validate_json(reponse.texte)
    except Exception as e:
        print(f"la sortie ne valide pas contre le schema Page : {type(e).__name__}")
        print("c'est exactement le cas que la boucle de reparation traite.")
        return 1

    print("\nPage valide du premier coup.")
    print(f"  titre_h1         : {page.titre_h1}")
    print(f"  meta_description : {len(page.meta_description)} caracteres")
    print(f"  blocs            : {[b.type for b in page.blocs]}")

    from fabrique.garde_fous.validateur import valider

    violations = valider(page, set())
    print(f"  violations       : {[v.code for v in violations] or 'aucune'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
