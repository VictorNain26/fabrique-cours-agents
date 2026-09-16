# A — Application de référence : implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre l'application de référence honnête et découplée : budget réel, fil rouge MCP branché, contexte compacté, graphe composé à la racine, API non bloquante.

**Architecture:** `construire()` reçoit ses dépendances en paramètres nommés avec des valeurs par défaut réelles. Un nœud `tarification` résout les prix via un client MCP en mémoire. La chaîne de fournisseurs est construite par une seule fabrique qui porte l'enveloppe de coût.

**Tech Stack:** Python 3.12, pydantic 2.13.5, langgraph 1.2.11, mcp 2.2.0, fastapi 0.141.1, pytest 9.1.1, ruff 0.16.7.

**Spec:** `docs/superpowers/specs/2026-09-16-parcours-apprenant-design.md` (section 1).

## Global Constraints

- Code, identifiants, commits en anglais pour les commits ; identifiants existants en français ASCII conservés (style du dépôt).
- Zéro commentaire sauf WHY non évident. Pas d'`eslint-disable`/`noqa`.
- Commits `<type>(<scope>): <description>`, stagés fichier par fichier, terminés par `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Validation finale de chaque tâche : `.venv/bin/pytest -q`, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .` à code de sortie 0.
- Aucun appel réseau réel ; ne jamais lire `.env`.
- Branche : `feat/reference-app-integrity`, créée depuis `docs/learner-journey-spec`.

---

### Task 1: Chaîne de fournisseurs unique avec enveloppe de coût

**Files:**
- Create: `fabrique/providers/chaine.py`
- Modify: `fabrique/config.py`, `fabrique/providers/anthropic.py:50-66`, `fabrique/api.py:76-96`, `fabrique/temporal/activites.py:20-40`, `.env.exemple`, `scripts_valider_fournisseur.py:47`
- Test: `tests/test_chaine.py` (create), `tests/test_config.py`, `tests/test_providers.py:240,294`

**Interfaces:**
- Produces: `fabrique.providers.chaine.chaine_depuis_reglages(parametres: Reglages) -> list[Fournisseur]`; `Reglages.cout_estime_ovhcloud: float`, `Reglages.cout_estime_anthropic: float`, `Reglages.budget_tokens_invite: int`; `Reglages.fournisseurs` refuse un nom hors `{"fake", "ovhcloud", "anthropic"}`; `FournisseurAnthropic(*, api_key, modele, ...)` avec `modele` obligatoire.

- [ ] **Step 1: Write the failing tests** — `tests/test_chaine.py` :

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from fabrique.config import Reglages
from fabrique.providers.anthropic import FournisseurAnthropic
from fabrique.providers.chaine import chaine_depuis_reglages
from fabrique.providers.fake import FournisseurFake
from fabrique.providers.ovhcloud import FournisseurOVHcloud


def test_la_chaine_suit_l_ordre_declare_et_porte_l_enveloppe() -> None:
    parametres = Reglages(
        fournisseurs="ovhcloud,anthropic,fake",
        ovh_api_key="k",
        anthropic_api_key="k",
        cout_estime_ovhcloud=0.002,
        cout_estime_anthropic=0.01,
    )

    chaine = chaine_depuis_reglages(parametres)

    assert [type(f) for f in chaine] == [FournisseurOVHcloud, FournisseurAnthropic, FournisseurFake]
    assert [f.cout_par_appel for f in chaine] == [0.002, 0.01, 0.0]
    assert chaine[1].modele == parametres.anthropic_modele


def test_un_nom_inconnu_est_refuse_a_la_frontiere() -> None:
    with pytest.raises(ValidationError, match="ovhclou"):
        Reglages(fournisseurs="ovhclou")


def test_le_budget_par_defaut_couvre_plusieurs_essais() -> None:
    parametres = Reglages()
    assert parametres.budget_par_page > 10 * max(
        parametres.cout_estime_ovhcloud, parametres.cout_estime_anthropic
    )


def test_anthropic_exige_un_modele() -> None:
    with pytest.raises(TypeError):
        FournisseurAnthropic(api_key="k")
```

- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_chaine.py -q` — Expected: FAIL (`ModuleNotFoundError: fabrique.providers.chaine`).

- [ ] **Step 3: Implement.** In `fabrique/config.py` add after `max_tours_correction` :

```python
    # Enveloppe debitee AVANT chaque essai, en euros. Estimee pour une page
    # (~1500 tokens en entree, ~800 en sortie) : OVHcloud 0,67 EUR/M tokens,
    # Haiku 4.5 1 $/M en entree et 5 $/M en sortie, arrondi au-dessus.
    cout_estime_ovhcloud: float = Field(default=0.002, ge=0)
    cout_estime_anthropic: float = Field(default=0.01, ge=0)
    budget_tokens_invite: int = Field(default=1500, ge=100)
```

and a validator (import `field_validator` from pydantic):

```python
    @field_validator("fournisseurs")
    @classmethod
    def _noms_connus(cls, valeur: str) -> str:
        inconnus = {n.strip() for n in valeur.split(",") if n.strip()} - FOURNISSEURS_CONNUS
        if inconnus:
            raise ValueError(f"fournisseurs inconnus : {sorted(inconnus)}")
        return valeur
```

with module constant `FOURNISSEURS_CONNUS = {"fake", "ovhcloud", "anthropic"}`.

Create `fabrique/providers/chaine.py` :

```python
"""Construit la chaine de repli declaree dans les reglages."""

from __future__ import annotations

from fabrique.config import Reglages
from fabrique.providers.anthropic import FournisseurAnthropic
from fabrique.providers.base import Fournisseur
from fabrique.providers.fake import FournisseurFake
from fabrique.providers.ovhcloud import FournisseurOVHcloud


def _un_fournisseur(nom: str, parametres: Reglages) -> Fournisseur:
    if nom == "ovhcloud":
        return FournisseurOVHcloud(
            api_key=parametres.ovh_api_key,
            base_url=parametres.ovh_base_url,
            modele=parametres.ovh_modele,
            cout_par_appel=parametres.cout_estime_ovhcloud,
        )
    if nom == "anthropic":
        return FournisseurAnthropic(
            api_key=parametres.anthropic_api_key,
            modele=parametres.anthropic_modele,
            cout_par_appel=parametres.cout_estime_anthropic,
        )
    return FournisseurFake()


def chaine_depuis_reglages(parametres: Reglages) -> list[Fournisseur]:
    return [_un_fournisseur(nom, parametres) for nom in parametres.chaine]
```

In `fabrique/providers/anthropic.py`, remove the default of `modele` (make it a required keyword argument; keep its position among keyword-only args). Replace `_un_fournisseur` / `_chaine_depuis_reglages` in `fabrique/api.py` and `fabrique/temporal/activites.py` with `from fabrique.providers.chaine import chaine_depuis_reglages` and drop the now-unused provider imports. In `scripts_valider_fournisseur.py:47` pass `modele=reglages().anthropic_modele` (import `reglages`). Add to `.env.exemple` under the budget block :

```
# Enveloppe estimee par appel, en euros, debitee avant l'essai.
COUT_ESTIME_OVHCLOUD=0.002
COUT_ESTIME_ANTHROPIC=0.01
# Taille maximale de l'invite de redaction, en tokens estimes.
BUDGET_TOKENS_INVITE=1500
```

Update `tests/test_providers.py:240` and `:294` to pass `modele="claude-haiku-4-5-20251001"`.

- [ ] **Step 4: Run** `.venv/bin/pytest -q && .venv/bin/ruff check . && .venv/bin/ruff format --check .` — Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add fabrique/providers/chaine.py fabrique/config.py fabrique/providers/anthropic.py fabrique/api.py fabrique/temporal/activites.py .env.exemple scripts_valider_fournisseur.py tests/test_chaine.py tests/test_providers.py
git commit -m "fix(providers): debit a real cost envelope and build the chain in one place"
```

### Task 2: Client MCP en mémoire et erreur d'outil attendue

**Files:**
- Create: `fabrique/mcp_catalogue/client.py`
- Modify: `fabrique/mcp_catalogue/serveur.py:52-58`
- Test: `tests/test_mcp_catalogue.py`

**Interfaces:**
- Produces: `fabrique.mcp_catalogue.client.resoudre_prix(reference: str) -> PrixResolu | None` (None si la référence est inconnue). `PrixResolu` reste défini dans `serveur.py`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_mcp_catalogue.py`) :

```python
def test_le_client_resout_le_prix_par_le_protocole() -> None:
    from fabrique.mcp_catalogue.client import resoudre_prix

    prix = resoudre_prix("vps-comfort")

    assert prix is not None
    assert prix.prix_mensuel_eur == catalogue.get("vps-comfort").prix_mensuel_eur


def test_le_client_rend_none_pour_une_reference_inconnue() -> None:
    from fabrique.mcp_catalogue.client import resoudre_prix

    assert resoudre_prix("inexistant") is None


@pytest.mark.asyncio
async def test_une_reference_inconnue_est_une_erreur_d_outil_nommee(serveur):
    from mcp import Client

    async with Client(serveur) as client:
        resultat = await client.call_tool("resoudre_prix", {"reference": "inexistant"})

    assert resultat.is_error is True
    assert "inexistant" in resultat.content[0].text
```

- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_mcp_catalogue.py -q` — Expected: 3 FAIL (module absent ; message générique « Error executing tool resoudre_prix » sans la référence, car `ValueError` est traitée comme un plantage : `mcp/server/mcpserver/tools/base.py:205-211`).

- [ ] **Step 3: Implement.** In `serveur.py` replace `raise ValueError(...)` by `raise ToolError(f"reference inconnue au catalogue: {reference}")` with `from mcp.server.mcpserver.exceptions import ToolError`. Create `client.py` :

```python
"""Client MCP de la fabrique : le graphe resout les prix par le protocole.

Connexion en memoire au serveur du catalogue (`mcp.Client` accepte une
instance `MCPServer`, docstring de mcp 2.2.0). Appele depuis du code
synchrone : l'API execute ses routes `def` dans un pool de threads, ou aucune
boucle asyncio ne tourne.
"""

from __future__ import annotations

import asyncio

from mcp import Client

from fabrique.mcp_catalogue.serveur import PrixResolu, construire


async def _resoudre(reference: str) -> PrixResolu | None:
    async with Client(construire()) as client:
        resultat = await client.call_tool("resoudre_prix", {"reference": reference})
    if resultat.is_error:
        return None
    return PrixResolu.model_validate(resultat.structured_content)


def resoudre_prix(reference: str) -> PrixResolu | None:
    return asyncio.run(_resoudre(reference))
```

- [ ] **Step 4: Run** `.venv/bin/pytest tests/test_mcp_catalogue.py -q` — Expected: PASS. Then full validation.

- [ ] **Step 5: Commit** `feat(mcp): resolve prices through an in-process MCP client`.

### Task 3: Graphe composé à la racine, contexte compacté, tarification

**Files:**
- Modify: `fabrique/modeles.py`, `fabrique/generation/graphe.py`, `fabrique/evaluation/evaluateurs.py:79-101`, `fabrique/evaluation/dataset.py` (références produit), `fabrique/evaluation/reference.json` (régénérée)
- Test: `tests/test_graphe.py`, `tests/test_observabilite_generations.py:88`, `tests/test_evaluation.py`

**Interfaces:**
- Consumes: `resoudre_prix` (Task 2), `compacter(messages, budget, resumer)` et `estimer(texte)` de `fabrique.generation.contexte`, `Reglages.budget_tokens_invite` (Task 1).
- Produces:

```python
def construire(
    fournisseurs: list[Fournisseur],
    pages_existantes: set[str],
    *,
    checkpointer=None,
    max_tours: int = 3,
    budget_par_page: float = 0.50,
    budget_tokens_invite: int = 1500,
    publier: Callable[[Page], str] = _publier_neutre,
    valider: Callable[[Page, set[str]], list[Violation]] = validateur.valider,
    generer: Callable[..., Page] = reparation.generer_valide,
    repli: Callable[..., Resultat] = repli_.executer,
    compacter: Callable[[list[dict], int, Callable[[list[dict]], str]], list[dict]] = contexte.compacter,
    resoudre_prix: Callable[[str], PrixResolu | None] = client_catalogue.resoudre_prix,
) -> CompiledStateGraph
```

`BlocPage.prix_affiche: SkipJsonSchema[str | None] = None`; `EtatPage.retours: Annotated[list[str], concat]`; nœuds `redaction, controle, correction, tarification, validation_humaine, publication`; violation `REF_PRODUIT_INCONNUE` (bloquant). `bloquantes` reste importé du module validateur (fonction pure, pas injectée).

Imports in `graphe.py` use module objects so defaults are looked up at call time:
`from fabrique.garde_fous import validateur`, `from fabrique.generation import contexte, reparation`, `from fabrique.mcp_catalogue import client as client_catalogue`, `from fabrique.providers import repli as repli_`. `bloquantes` : `validateur.bloquantes`. Keep `from fabrique.observabilite import observation, tracer_violation` (the observability test patches `fabrique.generation.graphe.tracer_violation`).

- [ ] **Step 1: Write the failing tests** — rewrite `tests/test_graphe.py` so every test builds the graph through a helper that injects doubles, and add the new behaviours :

```python
def _graphe(fournisseurs, **options):
    options.setdefault("checkpointer", InMemorySaver())
    options.setdefault("valider", _valider_titre_unique)
    options.setdefault("resoudre_prix", _prix_connus)
    return construire(fournisseurs, set(), **options)


def _valider_titre_unique(page, pages_existantes):
    titres = sum(1 for b in page.blocs if b.type == "titre")
    if titres == 1:
        return []
    return [Violation(code="H1_MULTIPLE", gravite="bloquant", message="titres", indice="un seul")]


def _prix_connus(reference):
    if reference != "vps-comfort":
        return None
    return PrixResolu(reference=reference, prix_mensuel_eur=7.99, libelle_affichable="7.99 EUR / mois")
```

New tests (plus the existing ones migrated to `_graphe`) :

```python
def test_la_tarification_renseigne_le_prix_depuis_le_resolveur():
    page = _page_avec_tableau("vps-comfort")
    graphe = _graphe([FournisseurFake(reponses=[page])])

    etat = graphe.invoke({"brief": "b"}, config=_config("prix-1"))

    blocs = etat["page"]["blocs"]
    assert [b["prix_affiche"] for b in blocs] == [None, "7.99 EUR / mois"]


def test_le_modele_ne_peut_pas_imposer_son_propre_prix():
    page = _page_avec_tableau("vps-comfort", prix_affiche="0.01 EUR")
    graphe = _graphe([FournisseurFake(reponses=[page])])

    etat = graphe.invoke({"brief": "b"}, config=_config("prix-2"))

    assert etat["page"]["blocs"][1]["prix_affiche"] == "7.99 EUR / mois"


def test_une_reference_inconnue_repart_en_correction():
    fournisseur = FournisseurFake(
        reponses=[_page_avec_tableau("inventee"), _page_avec_tableau("vps-comfort")]
    )
    graphe = _graphe([fournisseur])

    etat = graphe.invoke({"brief": "b"}, config=_config("prix-3"))

    assert etat["essais"] == 2
    assert "REF_PRODUIT_INCONNUE" in fournisseur.appels[1]["invite"]
    assert "__interrupt__" in etat


def test_les_retours_sont_compactes_sous_le_budget():
    vus = []

    def compacter_espion(messages, budget, resumer):
        vus.append((len(messages), budget))
        return messages

    fournisseur = FournisseurFake(reponses=[PAGE_INVALIDE, PAGE_INVALIDE, PAGE_VALIDE])
    graphe = _graphe([fournisseur], compacter=compacter_espion, budget_tokens_invite=321, max_tours=3)

    graphe.invoke({"brief": "b"}, config=_config("ctx-1"))

    assert vus == [(1, 321), (2, 321), (3, 321)]


def test_un_retour_ecarte_est_resume_par_ses_codes():
    fournisseur = FournisseurFake(reponses=[PAGE_INVALIDE, PAGE_INVALIDE, PAGE_VALIDE])
    graphe = _graphe([fournisseur], budget_tokens_invite=20, max_tours=3)

    graphe.invoke({"brief": "b" * 40}, config=_config("ctx-2"))

    derniere_invite = fournisseur.appels[2]["invite"]
    assert "retours precedents resumes : H1_MULTIPLE" in derniere_invite
    assert "retour_correction" not in derniere_invite


def test_les_dependances_injectees_sont_utilisees():
    appels = []

    def repli_espion(fournisseurs, budget, appel):
        appels.append(budget)
        return executer(fournisseurs, budget, appel)

    graphe = _graphe([FournisseurFake(reponses=[PAGE_VALIDE])], repli=repli_espion, budget_par_page=0.3)
    graphe.invoke({"brief": "b"}, config=_config("di-1"))

    assert appels == [0.3]
```

with helper :

```python
def _page_avec_tableau(reference, prix_affiche=None):
    return json.dumps({
        "titre_h1": "Titre",
        "meta_description": META,
        "blocs": [
            {"type": "titre", "contenu": "Titre unique"},
            {"type": "tableau_prix", "contenu": "Nos offres", "product_ref": reference,
             "prix_affiche": prix_affiche},
        ],
        "liens": [],
    })
```

The budget and fallback tests (`test_le_graphe_bascule...`, `test_le_budget_arrete...`) keep the default `repli` and are integration tests of chapters 4 and 6 (marker added in plan B). `test_tous_les_noeuds_sont_declares` adds `"tarification"`. In `tests/test_observabilite_generations.py:88` expected root spans become `["redaction", "controle", "correction", "redaction", "controle", "tarification", "publication"]`.

In `tests/test_evaluation.py` : `PAGE_BONNE`'s `tableau_prix` uses `"product_ref": "vps-comfort", "prix_affiche": "7.99 EUR / mois"`; add :

```python
    def test_prix_affiche_different_du_catalogue_est_note_zero(self):
        page = {**PAGE_BONNE, "blocs": [
            {"type": "titre", "contenu": "Titre"},
            {"type": "tableau_prix", "contenu": "Offres", "product_ref": "vps-comfort",
             "prix_affiche": "1.00 EUR / mois"},
        ]}
        assert refs_produit_resolues(input="brief", output=page).value == 0.0
```

and adapt the other `refs_produit_resolues` cases the same way (a `tableau_prix` without `prix_affiche` scores 0).

- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_graphe.py tests/test_evaluation.py -q` — Expected: FAIL on the new tests (`TypeError: unexpected keyword argument 'valider'`, missing `prix_affiche`).

- [ ] **Step 3: Implement.**

`fabrique/modeles.py` :

```python
from pydantic.json_schema import SkipJsonSchema


def _concatener(a: list[str] | None, b: list[str] | None) -> list[str]:
    return (a or []) + (b or [])


class BlocPage(BaseModel):
    type: TypeBloc
    contenu: str = Field(max_length=200)
    product_ref: str | None = None
    # Rempli par le noeud de tarification depuis le catalogue, jamais par le
    # modele : absent du schema envoye au LLM, et ecrase s'il l'invente.
    prix_affiche: SkipJsonSchema[str | None] = None
```

`EtatPage` : `journal: Annotated[list[str], _concatener]` and new `retours: Annotated[list[str], _concatener]`.

`fabrique/generation/graphe.py` — inside `construire` :

```python
    def resumer(ecartes: list[dict]) -> str:
        codes = sorted({ligne.split(":")[0].lstrip("- ") for m in ecartes
                        for ligne in m["contenu"].splitlines() if ligne.startswith("- ")})
        return "retours precedents resumes : " + ", ".join(codes)

    def invite_de(etat: EtatPage) -> str:
        messages = [{"role": "system", "contenu": etat["brief"], "tokens": contexte.estimer(etat["brief"])}]
        messages += [{"role": "user", "contenu": r, "tokens": contexte.estimer(r)} for r in etat.get("retours", [])]
        return "\n\n".join(m["contenu"] for m in compacter(messages, budget_tokens_invite, resumer))

    def noeud_redaction(etat):
        essais = etat.get("essais", 0) + 1
        invite = invite_de(etat)
        resultat = repli(fournisseurs, budget_par_page,
                         lambda f: generer(f, invite=invite, schema=Page, systeme=SYSTEME))
        ...same return as today...

    def noeud_controle(etat):
        page = Page.model_validate(etat["page"])
        violations = valider(page, pages_existantes)
        ...same as today...

    def noeud_correction(etat):
        violations = [Violation.model_validate(v) for v in etat.get("violations", [])]
        lignes = [f"- {v.code}: {v.message} {v.indice}".rstrip() for v in validateur.bloquantes(violations)]
        return {"retours": ["retour_correction:\n" + "\n".join(lignes)],
                "journal": [f"correction: {len(lignes)} retour(s)"]}

    def noeud_tarification(etat):
        page = Page.model_validate(etat["page"])
        inconnues = []
        blocs = []
        for bloc in page.blocs:
            prix = None
            if bloc.type == "tableau_prix" and bloc.product_ref:
                resolu = resoudre_prix(bloc.product_ref)
                if resolu is None:
                    inconnues.append(bloc.product_ref)
                else:
                    prix = resolu.libelle_affichable
            blocs.append(bloc.model_copy(update={"prix_affiche": prix}))
        violations = [
            Violation(code="REF_PRODUIT_INCONNUE", gravite="bloquant",
                      message=f"La reference '{r}' n'existe pas au catalogue.",
                      indice="Utilise une reference du catalogue (chercher_produit).")
            for r in inconnues
        ]
        return {"page": page.model_copy(update={"blocs": blocs}).model_dump(),
                "violations": [v.model_dump() for v in violations],
                "journal": [f"tarification: {len(blocs)} bloc(s), {len(inconnues)} reference(s) inconnue(s)"]}
```

Routing : `controle` → `correction` if blocking and `bornes`, else `tarification` ; `tarification` → `correction` if blocking and `bornes`, else `validation_humaine`. Both use the same `route_bloquante(suivant)` factory :

```python
    def route_si_bloquant(suivant: str):
        def route(etat: EtatPage) -> str:
            violations = [Violation.model_validate(v) for v in etat.get("violations", [])]
            if validateur.bloquantes(violations) and bornes(etat):
                return "correction"
            return suivant
        return route
```

Wire `graphe.add_conditional_edges("controle", route_si_bloquant("tarification"), ["correction", "tarification"])` and `graphe.add_conditional_edges("tarification", route_si_bloquant("validation_humaine"), ["correction", "validation_humaine"])`. Wrap `tarification` with `_observe`. Remove `_dernier_retour`, `Overwrite` import and its WHY comment. Update the module docstring flow.

`evaluateurs.refs_produit_resolues` : a `tableau_prix` block scores 0 unless `product_ref` exists in `catalogue` and `prix_affiche == f"{produit.prix_mensuel_eur:.2f} EUR / mois"` ; comment lists the offending blocks. `_bloc_comme_bloc_page` keeps working (`model_construct` accepts `prix_affiche`).

`dataset.py` : replace `refs_produit_attendues` values with catalogue references (`hebergement-mutualise`→`vps-starter`, `vps-petit`→`vps-starter`, `vps-moyen`→`vps-comfort`, `vps-grand`→`vps-elite`, `stockage-objet`→`stockage-standard`) and add a test in `tests/test_evaluation.py` :

```python
def test_le_dataset_ne_cite_que_des_references_du_catalogue():
    from fabrique.evaluation.dataset import CAS
    from fabrique.mcp_catalogue import catalogue

    for cas in CAS:
        for ref in cas["metadata"].get("refs_produit_attendues", []):
            assert catalogue.get(ref) is not None, ref
```

(adapt the key access to the real `CasGolden` shape in `dataset.py`).

- [ ] **Step 4: Run** `.venv/bin/pytest -q`, then `.venv/bin/python -m fabrique.evaluation.ci`. If the gate reports a changed average, inspect why; regenerate only if the new value is the intended consequence: `.venv/bin/python -m fabrique.evaluation.ci --ecrire-reference`, and record the diff in the commit body.

- [ ] **Step 5: Commit** `feat(graph): compose dependencies at the root, compact feedback and resolve prices via MCP`.

### Task 4: API non bloquante et observabilité paramétrable

**Files:**
- Modify: `fabrique/api.py` (routes `async def` → `def`), `fabrique/observabilite.py:43-75`
- Test: `tests/test_api.py`, `tests/test_observabilite.py`

**Interfaces:**
- Produces: `observation(nom, *, as_type="span", fil=None, trace="page", **attributs)`.

- [ ] **Step 1: Write the failing tests.** `tests/test_api.py` :

```python
def test_une_page_avec_tableau_de_prix_passe_par_mcp_via_l_api(client, monkeypatch) -> None:
    import json
    from fabrique.providers.fake import FournisseurFake

    page = json.dumps({"titre_h1": "VPS", "meta_description": "d" * 130, "blocs": [
        {"type": "titre", "contenu": "VPS"},
        {"type": "tableau_prix", "contenu": "Offres", "product_ref": "vps-pro"}], "liens": []})
    client.app.state.fournisseurs = [FournisseurFake(reponses=[page])]

    corps = client.post("/pages", json={"brief": "b"}).json()

    assert corps["page"]["blocs"][1]["prix_affiche"] == "31.99 EUR / mois"


def test_les_routes_ne_bloquent_pas_la_boucle() -> None:
    import inspect
    from fabrique import api

    for route in (api.sante, api.creer_page, api.lire_page, api.valider_page):
        assert not inspect.iscoroutinefunction(route), route.__name__
```

`tests/test_observabilite.py` : add a test using the in-memory exporter fixture pattern of `tests/test_observabilite_generations.py` (copy its `spans` fixture into a shared `tests/conftest.py`, and import nothing from test modules) asserting that `observation("x", fil="f", trace="tuteur")` produces a trace whose name attribute is `tuteur`. Read the attribute key used by langfuse 4.15.3 from `.venv/lib/python3.12/site-packages/langfuse/_client/attributes.py` (constant for trace name) before writing the assertion.

- [ ] **Step 2: Run** — Expected: FAIL (`RuntimeError: asyncio.run() cannot be called from a running event loop` for the first test ; coroutine assertion for the second ; unknown kwarg `trace`).

- [ ] **Step 3: Implement.** Change the four route functions and the exception handlers stay `async`. Add `trace: str = NOM_TRACE` to `observation` and use it in `propagate_attributes(trace_name=trace, ...)`.

- [ ] **Step 4: Run** full validation and the gate.

- [ ] **Step 5: Commit** `fix(api): run routes in the threadpool so graph nodes can call MCP`.

### Task 5: Documentation alignée

**Files:**
- Modify: `README.md`, `docs/verification.md`

- [ ] **Step 1:** README : flux avec `tarification`, fil rouge MCP réel, budget réel (enveloppes `COUT_ESTIME_*`), routes synchrones. Retirer toute phrase devenue fausse ; ne rien affirmer qui n'a pas tourné. `docs/verification.md` : ajouter les deux sources (FastAPI async, `mcp.Client` en mémoire, `ToolError`) avec niveau `doc` ou `execute`.
- [ ] **Step 2:** `.venv/bin/pytest -q` (le test `.env.exemple` couvre la cohérence config).
- [ ] **Step 3: Commit** `docs: describe the MCP pricing step and the real budget envelope`.
