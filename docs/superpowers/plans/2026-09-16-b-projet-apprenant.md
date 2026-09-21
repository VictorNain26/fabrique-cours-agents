# B — Projet apprenant et moteur du cours : implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** L'apprenant construit son propre projet, dans un dépôt git à lui, chapitre après chapitre, et peut le publier sur GitHub à la fin.

**Architecture:** Un paquet `parcours/` (dans le cours) génère le projet, installe les tests d'un chapitre, lance la vérification dans un sous-processus où le `fabrique` du projet masque celui de la référence, rattrape un chapitre et prépare la publication. `cours.py` n'est plus qu'une interface terminal au-dessus de `parcours/`. Les chapitres sont renumérotés dans l'ordre des imports ; ce plan pose la structure (ordre, squelettes, correcteurs, marqueurs de tests), le plan C réécrit la prose.

**Tech Stack:** Python 3.12 stdlib (subprocess, ast, shutil, json, tomllib), pytest 9.1.1, ruff 0.16.7, git, gh 2.96.0.

**Spec:** `docs/superpowers/specs/2026-09-16-parcours-apprenant-design.md` (sections 2, 3, 5).

## Global Constraints

- Ordre des chapitres (numéro → module écrit) : 0 aucun ; 1 `fabrique/generation/reparation.py` ; 2 `fabrique/garde_fous/validateur.py` ; 3 `fabrique/mcp_catalogue/serveur.py` ; 4 `fabrique/providers/repli.py` ; 5 `fabrique/generation/contexte.py` ; 6 `fabrique/generation/graphe.py` ; 7 `fabrique/generation/reprise.py` ; 8 `fabrique/api.py` ; 9 `fabrique/observabilite.py` ; 10 `fabrique/evaluation/experience.py` ; 11 `fabrique/evaluation/ci.py` ; 12 `fabrique/temporal/workflows.py`.
- Un chapitre n'importe que des modules fournis ou écrits dans un chapitre de numéro inférieur.
- Le projet de l'apprenant ne contient ni `contenu/`, ni `cours.py`, ni `parcours/`, ni `docs/superpowers/`, ni `tests/test_parcours.py`, ni `tests/test_tuteur.py`, ni `tests/test_providers_reels.py`, ni les solutions des 12 modules (sauf rattrapage explicite).
- Squelettes : importables, `ruff check` et `ruff format --check` propres, mêmes noms publics et mêmes signatures que la référence, `raise NotImplementedError("chapitre N")` dans les corps à écrire, jamais à l'import.
- Texte affiché à l'apprenant : français accentué. Identifiants : français ASCII (style du dépôt). Commits : anglais, conventionnels, `Co-Authored-By: Claude <noreply@anthropic.com>` pour les commits de ce plan (pas pour ceux que `cours.py` crée dans le projet de l'apprenant).
- Validation de chaque tâche : `.venv/bin/pytest -q`, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/python -m fabrique.evaluation.ci`, codes de sortie 0.
- Ne jamais lire `.env`. Aucun appel réseau réel. Les sous-processus git des tests fixent `GIT_AUTHOR_NAME`, `GIT_AUTHOR_EMAIL`, `GIT_COMMITTER_NAME`, `GIT_COMMITTER_EMAIL` et `GIT_CONFIG_GLOBAL=/dev/null`.
- Branche : `feat/learner-project`, créée depuis `feat/reference-app-integrity`.

---

### Task 1: Marqueurs de chapitres sur la suite de tests

**Files:**
- Modify: `pyproject.toml` (`[tool.pytest.ini_options]`), every `tests/test_*.py` except `test_providers_reels.py`
- Create: `parcours/__init__.py` (vide), `parcours/manifeste.py`
- Test: `tests/test_parcours.py` (create)

**Interfaces:**
- Produces: marker `chapitres(*numeros)` registered in pyproject; `parcours.manifeste.chapitres_du_test(chemin: Path) -> frozenset[int]` (reads `pytestmark` by `ast`, no import) ; `parcours.manifeste.MODULES: dict[int, str]` (numéro → chemin relatif du module, cf. Global Constraints) ; `parcours.manifeste.TESTS_COURS: frozenset[str]` = `{"test_parcours.py", "test_tuteur.py", "test_providers_reels.py"}`.

- [ ] **Step 1: Write the failing tests** in `tests/test_parcours.py` :

```python
from __future__ import annotations

from pathlib import Path

from parcours.manifeste import MODULES, TESTS_COURS, chapitres_du_test

RACINE = Path(__file__).resolve().parent.parent
TESTS = sorted(p for p in (RACINE / "tests").glob("test_*.py") if p.name not in TESTS_COURS)


def test_chaque_fichier_de_test_declare_ses_chapitres():
    for chemin in TESTS:
        chapitres = chapitres_du_test(chemin)
        assert chapitres <= set(range(0, 13)), chemin.name


def test_un_test_ne_depend_que_de_chapitres_existants_et_ordonnes():
    for chemin in TESTS:
        assert all(n == 0 or n in MODULES for n in chapitres_du_test(chemin)), chemin.name


def test_les_modules_de_chapitre_existent():
    assert sorted(MODULES) == list(range(1, 13))
    for chemin in MODULES.values():
        assert (RACINE / chemin).is_file(), chemin
```

and in `parcours/manifeste.py` the reader must treat `pytestmark = pytest.mark.chapitres(0)` as "fourni" (`{0}`), and a file without `pytestmark` as an error (`ValueError` naming the file), tested with a `tmp_path` file :

```python
def test_un_fichier_sans_marqueur_est_refuse(tmp_path):
    import pytest

    fichier = tmp_path / "test_x.py"
    fichier.write_text("def test_a():\n    pass\n")
    with pytest.raises(ValueError, match="test_x.py"):
        chapitres_du_test(fichier)
```

- [ ] **Step 2: Run** `.venv/bin/pytest tests/test_parcours.py -q` — Expected: FAIL (`ModuleNotFoundError: parcours`).

- [ ] **Step 3: Implement.** `pyproject.toml` :

```toml
markers = [
    "chapitres(*numeros): chapitres du cours dont ce fichier de tests depend (0 = fourni)",
]
```

`parcours/manifeste.py` :

```python
"""Ce que le cours sait de l'application : quel chapitre ecrit quel module,
et de quels chapitres depend chaque fichier de tests."""

from __future__ import annotations

import ast
from pathlib import Path

MODULES: dict[int, str] = {
    1: "fabrique/generation/reparation.py",
    2: "fabrique/garde_fous/validateur.py",
    3: "fabrique/mcp_catalogue/serveur.py",
    4: "fabrique/providers/repli.py",
    5: "fabrique/generation/contexte.py",
    6: "fabrique/generation/graphe.py",
    7: "fabrique/generation/reprise.py",
    8: "fabrique/api.py",
    9: "fabrique/observabilite.py",
    10: "fabrique/evaluation/experience.py",
    11: "fabrique/evaluation/ci.py",
    12: "fabrique/temporal/workflows.py",
}

TESTS_COURS = frozenset({"test_parcours.py", "test_tuteur.py", "test_providers_reels.py"})


def chapitres_du_test(chemin: Path) -> frozenset[int]:
    arbre = ast.parse(chemin.read_text())
    for noeud in arbre.body:
        if (
            isinstance(noeud, ast.Assign)
            and any(isinstance(c, ast.Name) and c.id == "pytestmark" for c in noeud.targets)
            and isinstance(noeud.value, ast.Call)
            and isinstance(noeud.value.func, ast.Attribute)
            and noeud.value.func.attr == "chapitres"
        ):
            return frozenset(ast.literal_eval(a) for a in noeud.value.args)
    raise ValueError(f"{chemin.name} ne declare pas pytestmark = pytest.mark.chapitres(...)")
```

Add `pytestmark = pytest.mark.chapitres(...)` right after the imports of each test file (add `import pytest` where missing), with these sets — derived from what each file imports at module level and what its tests exercise :

| Fichier | chapitres |
|---|---|
| test_config.py, test_chaine.py, test_providers.py | 0 |
| test_reparation.py | 1 |
| test_validateur.py | 2 |
| test_mcp_catalogue.py | 3 |
| test_repli.py | 4 |
| test_contexte.py | 5 |
| test_graphe.py | 1, 4, 5, 6 |
| test_reprise.py | 1, 2, 3, 4, 5, 6, 7 |
| test_api.py | 1, 2, 3, 4, 5, 6, 7, 8 |
| test_observabilite.py, test_observabilite_reseau.py | 9 |
| test_observabilite_generations.py | 1, 2, 3, 4, 5, 6, 9 |
| test_evaluation.py | 2, 10 |
| test_ci.py | 1, 2, 3, 4, 5, 6, 10, 11 |
| test_temporal.py | 1, 2, 4, 12 |

Before writing each set, read the file's imports and adjust the set if it imports a chapter module the table misses (e.g. `test_providers.py` must not import `repli`; if it does, mark it 4). Record any deviation in the report.

- [ ] **Step 4: Run** full validation.
- [ ] **Step 5: Commit** `test: declare which course chapters each test file depends on`.

### Task 2: Nouvel ordre des chapitres et squelettes alignés sur la référence

**Files:**
- Rename (git mv) : `contenu/ch01.py`→`ch01.py` (reparation), `ch05.py`→`ch02.py`, `ch06.py`→`ch03.py`, `ch08.py`→`ch04.py`, `ch03.py`→`ch05.py`, `ch02.py`→`ch06.py`, `ch09.py`→`ch07.py`, `ch10.py`→`ch08.py`, `ch11.py`→`ch09.py`, `ch07.py`→`ch10.py`, `ch12.py`→`ch11.py`, `ch04.py`→`ch12.py` (use a temporary name to avoid collisions); constants `CHn`/`SQn`/`verifn` renamed to the new number; `numero=` updated.
- Create: `contenu/ch00.py` (chapitre 0, sans atelier, texte minimal : titre « La fabrique en marche », objectif, un bloc qui dit de lancer `python3 cours.py --nouveau ~/ma-fabrique` ; le plan C l'écrit en entier).
- Modify: `contenu/__init__.py`, `modele.py`, every `contenu/chNN.py` skeleton and `verifN`
- Test: `tests/test_parcours.py`

**Interfaces:**
- Consumes: `MODULES` (Task 1).
- Produces in `modele.py` :

```python
@dataclass
class Kata:
    consigne: str
    squelette: str
    verifier: Callable[[object], list[tuple[bool, str]]]
    module: str
    message_commit: str
    indices: list[str] = field(default_factory=list)
    notes_tuteur: str = ""
    dependances: list[str] = field(default_factory=list)


@dataclass
class Question:
    enonce: str
    options: list[str]
    bonne: int | list[int]
    explication: str
    kind: str = "choix"  # "choix" | "ordre"
    source: str = ""


@dataclass
class Chapitre:
    ...existing fields...
    predictions: list[Question] = field(default_factory=list)
```

`Kata.module` is now the dotted module name (`"fabrique.garde_fous.validateur"`), required; `fichier`, `solution` and `indice` disappear (`indice` becomes `indices=[...]`, keep the existing hint text as the single element for now). For `kind="ordre"`, `options` are shown shuffled and `bonne` is the list of option indexes in the right order.

`message_commit` per chapter: 1 `feat(generation): repair invalid model output with a bounded loop`; 2 `feat(guardrails): add deterministic page validator`; 3 `feat(mcp): expose the product catalogue as an MCP server`; 4 `feat(providers): add fallback chain under a cost budget`; 5 `feat(generation): compact prompt context under a token budget`; 6 `feat(graph): build the page generation graph`; 7 `feat(generation): resume a paused run after human review`; 8 `feat(api): expose generation and review over HTTP`; 9 `feat(observability): trace pages in Langfuse`; 10 `feat(evaluation): score the golden dataset`; 11 `ci: add a non-regression gate`; 12 `feat(temporal): add a deterministic generation workflow`.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_parcours.py`) :

```python
import importlib
import importlib.util
import inspect
import subprocess
import sys
import types

import pytest

from contenu import CHAPITRES

KATAS = [ch for ch in CHAPITRES if ch.kata is not None]


def _charger_squelette(chapitre) -> types.ModuleType:
    module = types.ModuleType(f"squelette_{chapitre.numero}")
    exec(
        compile(chapitre.kata.squelette, f"<squelette {chapitre.numero}>", "exec"), module.__dict__
    )
    return module


def test_les_chapitres_suivent_l_ordre_du_manifeste():
    assert [ch.numero for ch in CHAPITRES] == list(range(0, 13))
    for ch in KATAS:
        assert ch.kata.module.replace(".", "/") + ".py" == MODULES[ch.numero]


@pytest.mark.parametrize("chapitre", KATAS, ids=lambda c: f"ch{c.numero:02d}")
def test_le_squelette_s_importe_et_expose_la_meme_interface(chapitre):
    squelette = _charger_squelette(chapitre)
    reference = importlib.import_module(chapitre.kata.module)
    publics_ref = {
        nom: v
        for nom, v in vars(reference).items()
        if not nom.startswith("_")
        and getattr(v, "__module__", None) == reference.__name__
        and (inspect.isfunction(v) or inspect.isclass(v))
    }
    publics_sq = {
        nom: v
        for nom, v in vars(squelette).items()
        if not nom.startswith("_")
        and getattr(v, "__module__", None) == squelette.__name__
        and (inspect.isfunction(v) or inspect.isclass(v))
    }
    assert set(publics_sq) == set(publics_ref)
    for nom, valeur in publics_ref.items():
        if inspect.isfunction(valeur):
            assert str(inspect.signature(publics_sq[nom])) == str(inspect.signature(valeur)), nom


@pytest.mark.parametrize("chapitre", KATAS, ids=lambda c: f"ch{c.numero:02d}")
def test_le_squelette_est_propre_pour_ruff(chapitre, tmp_path):
    fichier = tmp_path / Path(MODULES[chapitre.numero]).name
    fichier.write_text(chapitre.kata.squelette.lstrip("\n"))
    for commande in (["check"], ["format", "--check"]):
        sortie = subprocess.run(
            [
                sys.executable,
                "-m",
                "ruff",
                *commande,
                "--config",
                str(RACINE / "pyproject.toml"),
                str(fichier),
            ],
            capture_output=True,
            text=True,
        )
        assert sortie.returncode == 0, sortie.stdout + sortie.stderr


@pytest.mark.parametrize("chapitre", KATAS, ids=lambda c: f"ch{c.numero:02d}")
def test_le_correcteur_passe_sur_la_reference(chapitre):
    resultats = chapitre.kata.verifier(importlib.import_module(chapitre.kata.module))
    echecs = [message for ok, message in resultats if not ok]
    assert resultats and not echecs, echecs
```

Factor the two identical dict comprehensions into one `_publics(module)` helper when implementing. The "correcteur fails cleanly on the skeleton" check needs the project mechanism and lives in Task 4.

- [ ] **Step 2: Run** — Expected: FAIL (chapter order, skeleton interfaces, ruff on skeletons).

- [ ] **Step 3: Implement.** Do the renames; update each skeleton to the CURRENT reference module (after plan A): same imports that are actually used, same public names and signatures, bodies to write replaced by `raise NotImplementedError("chapitre N")`. Fading of guidance: chapters 1–3 keep most of the module and leave one or two function bodies to write; chapters 4–8 leave the core function(s); chapters 9–12 leave most of the module. Specific rules :
  - Ch 6 (graphe) : `construire` signature identical to the reference (dependency injection parameters included); `validation_humaine` and `publication` node bodies are PROVIDED (interrupt is taught in chapter 7) with a one-line comment saying so; the learner writes `redaction`, `controle`, `correction`, `tarification`, routing and wiring.
  - Ch 9 (observabilite) : the inactive branch (`actif()` false → yield `_rien`) and `actif()` are written; the Langfuse branch of `observation` and the body of `tracer_violation` after the `actif()` guard raise `NotImplementedError("chapitre 9")` — so every provider keeps working without keys.
  - Ch 8 (api) : models, exception handlers and `lifespan` provided; route bodies to write.
  - Ch 12 (workflows) : timeouts/retry constants provided; `run` body to write.
  - Skeleton imports must not create ruff F401: import only what the provided code uses, and tell the learner in the skeleton's docstring what to import.
  Update every `verifN` so it passes on the reference (Step 1 test), uses the current APIs (e.g. `FOURNISSEURS` not `FOURNISSEUR`, `reglages().dsn`, `mcp.server.MCPServer`), sets `LANGFUSE_PUBLIC_KEY=""`/`LANGFUSE_SECRET_KEY=""` via `os.environ` and `reglages.cache_clear()` where observability is involved (so a learner's `.env` never changes the verdict), and replaces source-substring checks (`"retry_policy" in src`, `count("start_to_close_timeout")`, `"pas" in d`) by behavioural or AST checks. Extend chapter 12's forbidden calls with `datetime.datetime.now`, `datetime.now`, `time.time_ns`, `random.uniform`, `uuid.uuid1`. Ch 11's corrector exercises the `RegressionError` path and `--ecrire-reference` in a `tmp_path`. Ch 9's corrector exercises the active branch with an in-memory OpenTelemetry exporter (reuse the `spans` fixture logic from `tests/conftest.py`). Every failure message states what was expected and what was observed. `cours.py` is updated only as far as needed to keep importing (`kata.indices[0]` instead of `kata.indice`; `jouer_quiz` accepts `kind="ordre"`: the learner types the letters in order, e.g. `cab`).

- [ ] **Step 4: Run** full validation + gate.
- [ ] **Step 5: Commit** `refactor(course): reorder chapters along the import graph and align skeletons with the app`.

### Task 3: Génération du projet de l'apprenant

**Files:**
- Create: `parcours/projet.py`, `parcours/modele_projet/README.md`, `parcours/modele_projet/gitignore`, `parcours/modele_projet/pyproject.toml`, `parcours/modele_projet/ci.yml`
- Test: `tests/test_parcours.py`

**Interfaces:**
- Consumes: `MODULES`, `chapitres_du_test`, `TESTS_COURS` (Task 1), `CHAPITRES` / `Kata.squelette` (Task 2).
- Produces :

```python
FOURNIS: tuple[str, ...]  # chemins relatifs copiés tels quels

def creer(dossier: Path, *, racine: Path = RACINE, auteur: str) -> None
def tests_a_installer(chapitre: int, faits: set[int], *, racine: Path = RACINE) -> list[str]
def installer_tests(projet: Path, chapitre: int, faits: set[int], *, racine: Path = RACINE) -> list[str]
def git(projet: Path, *args: str) -> subprocess.CompletedProcess[str]
def commiter(projet: Path, fichiers: list[str], message: str) -> str  # renvoie le sha court
```

`FOURNIS` = `fabrique/__init__.py` and every package `__init__.py`, `fabrique/modeles.py`, `fabrique/config.py`, `fabrique/providers/{base,fake,ovhcloud,anthropic,chaine}.py`, `fabrique/mcp_catalogue/{catalogue,client}.py`, `fabrique/evaluation/{dataset,evaluateurs}.py`, `fabrique/evaluation/reference.json`, `fabrique/temporal/{activites,worker}.py`, `Dockerfile`, `docker-compose.yml`, `.env.exemple`, `requirements.txt`, `requirements-dev.txt`, and every `tests/test_*.py` whose chapters are `{0}`.

`creer` : refuses an existing non-empty `dossier` (`FileExistsError`); copies `FOURNIS`; writes each chapter module from its skeleton (`squelette.lstrip("\n")`); writes `pyproject.toml` from the template with `name` = slug of the folder name; writes `.gitignore`, `README.md` (template placeholders `{nom}` and `{auteur}` via `str.format`); `git init -b main`, stages every file one by one, commits `chore: scaffold the page factory project`. The workflow template `ci.yml` is NOT installed here (chapter 11 installs it). `tests/conftest.py` from the course is copied too if it exists (it is shared test infrastructure).

`tests_a_installer(n, faits)` returns course test files (names) whose chapter set contains `n`, whose other chapters are all in `faits`, and which are not in `TESTS_COURS`, sorted.

`installer_tests` copies them into `projet/tests/` (overwriting) and returns the names; for chapter 11 it also writes `.github/workflows/ci.yml` from the template.

`commiter` runs `git add -- <f>` for each file, then `git commit -m <message>`, returns `git rev-parse --short HEAD`.

Templates :
- `pyproject.toml` : `[project] name`, `requires-python = ">=3.10"`, the same `[tool.ruff]`, `[tool.ruff.lint]` and `[tool.pytest.ini_options]` as the course's pyproject (without `.solutions`/`atelier` excludes), including the `chapitres` marker.
- `gitignore` : `.venv/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`, `.ruff_cache/`, `.env`.
- `ci.yml` : copy of the course's `.github/workflows/ci.yml` (same pinned actions), steps: install, `ruff check .`, `ruff format --check .`, `pytest -q`, `python -m fabrique.evaluation.ci`.
- `README.md` : a project README written for a portfolio, in French: title `# {nom}`, one-paragraph pitch (service qui génère des pages web avec des agents IA sous garde-fous : validation déterministe, prix résolus par un serveur MCP, repli entre fournisseurs sous budget, validation humaine, traces Langfuse, porte de non-régression en CI), the flow diagram of the graph, a stack table, « Démarrer » (venv, `pytest -q`, `docker compose up --build`, `curl localhost:8000/sante`), « Routes », « Ce que coûte une page » (link to the numbers in the course README, not copied), « Tests et CI », « Auteur : {auteur} », and one closing line « Construit en suivant le cours *Agents IA en production* ». No course mechanics.

- [ ] **Step 1: Write the failing tests** :

```python
import os

ENV_GIT = {
    **os.environ,
    "GIT_AUTHOR_NAME": "Test",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Test",
    "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
}


@pytest.fixture
def env_git(monkeypatch):
    for cle, valeur in ENV_GIT.items():
        monkeypatch.setenv(cle, valeur)


def test_creer_un_projet_sans_contenu_de_cours(tmp_path, env_git):
    from parcours.projet import creer, git

    projet = tmp_path / "ma-fabrique"
    creer(projet, auteur="Ada")

    suivis = set(git(projet, "ls-files").stdout.split())
    assert "fabrique/modeles.py" in suivis
    assert all(chemin in suivis for chemin in MODULES.values())
    assert not any(c.startswith(("contenu/", "parcours/", "docs/")) for c in suivis)
    assert "cours.py" not in suivis and ".github/workflows/ci.yml" not in suivis
    assert "tests/test_parcours.py" not in suivis
    assert "Ada" in (projet / "README.md").read_text()
    assert (
        git(projet, "log", "--format=%s").stdout.strip()
        == "chore: scaffold the page factory project"
    )
    for n, chemin in MODULES.items():
        assert 'NotImplementedError("chapitre' in (projet / chemin).read_text(), n


def test_un_dossier_non_vide_est_refuse(tmp_path, env_git):
    from parcours.projet import creer

    (tmp_path / "x").write_text("")
    with pytest.raises(FileExistsError):
        creer(tmp_path, auteur="Ada")


def test_le_projet_neuf_passe_sa_suite_et_ruff(tmp_path, env_git):
    from parcours.projet import creer

    projet = tmp_path / "p"
    creer(projet, auteur="Ada")
    for commande in (
        ["pytest", "-q", "-p", "no:cacheprovider"],
        ["ruff", "check", "."],
        ["ruff", "format", "--check", "."],
    ):
        sortie = subprocess.run(
            [sys.executable, "-m", *commande],
            cwd=projet,
            capture_output=True,
            text=True,
            env={**ENV_GIT, "PYTHONPATH": str(projet)},
        )
        assert sortie.returncode == 0, sortie.stdout[-3000:] + sortie.stderr[-3000:]


def test_les_tests_arrivent_quand_leurs_chapitres_sont_faits():
    from parcours.projet import tests_a_installer

    assert tests_a_installer(2, faits={1}) == ["test_validateur.py"]
    assert "test_graphe.py" not in tests_a_installer(6, faits={1, 4})
    assert "test_graphe.py" in tests_a_installer(6, faits={1, 4, 5})
```

- [ ] **Step 2: Run** — Expected: FAIL (`ModuleNotFoundError: parcours.projet`).
- [ ] **Step 3: Implement** as specified.
- [ ] **Step 4: Run** full validation + gate.
- [ ] **Step 5: Commit** `feat(course): generate the learner's own project`.

### Task 4: Vérification isolée, rattrapage

**Files:**
- Create: `parcours/verification.py`, `parcours/correcteur.py`
- Modify: `parcours/projet.py` (add `rattraper`), `tests/test_temporal.py` (`execution_timeout`)
- Test: `tests/test_parcours.py`

**Interfaces:**
- Produces :

```python
@dataclass(frozen=True)
class Verdict:
    lignes: list[tuple[bool, str]]
    sortie_tests: str
    tests_ok: bool

    @property
    def ok(self) -> bool: ...  # lignes non vides, toutes vraies, et tests_ok

def verifier(projet: Path, chapitre: int, faits: set[int], *, racine: Path = RACINE, delai: float = 300) -> Verdict
def rattraper(projet: Path, chapitre: int, faits: set[int], *, racine: Path = RACINE) -> str  # sha
```

`parcours/correcteur.py` is a script run as `python -m parcours.correcteur N` with `cwd=projet` and `PYTHONPATH=f"{projet}{os.pathsep}{racine}"` (project first, so `fabrique` is the learner's): it imports `contenu`, finds chapter N, imports `kata.module`, runs `kata.verifier`, and prints one JSON line `{"lignes": [[ok, message], ...]}`. `NotImplementedError` becomes `[[false, "pas encore implémenté : <message>"]]`; `AssertionError` becomes `[[false, str(e)]]`; any other exception becomes `[[false, "le correcteur a planté sur ton code : <4 dernières lignes de la trace>"]]`. Exit code 0 in all these cases.

`verifier` installs the chapter's tests (`installer_tests`), runs the corrector subprocess, then `python -m pytest -q -p no:cacheprovider <tests installés>` in the project with the same `PYTHONPATH`, both with `timeout=delai`; a timeout becomes a failed line `("délai dépassé (<delai> s) : un appel bloque, souvent un NotImplementedError dans un workflow", False)`. Environment of both subprocesses: current env with `LANGFUSE_PUBLIC_KEY=""`, `LANGFUSE_SECRET_KEY=""`, `FOURNISSEURS="fake"`, `POSTGRES_HOST=""`.

`rattraper(projet, n, faits)` copies the reference module `racine / MODULES[n]` into the project, installs the chapter's tests, and commits both with `chore(course): use reference solution for chapter {n}`.

`tests/test_temporal.py` : every `execute_workflow` call gets `execution_timeout=timedelta(seconds=30)` so a skeleton workflow fails instead of hanging (source to cite in the commit body: temporalio `Client.execute_workflow` parameter, read in `.venv/lib/python3.12/site-packages/temporalio/client.py`).

- [ ] **Step 1: Write the failing tests** :

```python
@pytest.mark.parametrize("chapitre", KATAS, ids=lambda c: f"ch{c.numero:02d}")
def test_le_squelette_echoue_proprement_et_la_reference_passe(chapitre, tmp_path, env_git):
    from parcours.projet import creer, rattraper
    from parcours.verification import verifier

    projet = tmp_path / "p"
    creer(projet, auteur="Ada")
    faits = set()
    for n in range(1, chapitre.numero):
        rattraper(projet, n, faits)
        faits.add(n)

    avant = verifier(projet, chapitre.numero, faits, delai=120)
    assert not avant.ok
    assert avant.lignes and not any("planté" in m for _, m in avant.lignes), avant.lignes

    rattraper(projet, chapitre.numero, faits)
    apres = verifier(projet, chapitre.numero, faits, delai=120)
    assert apres.ok, (apres.lignes, apres.sortie_tests[-3000:])


def test_le_rattrapage_est_visible_dans_l_historique(tmp_path, env_git):
    from parcours.projet import creer, git, rattraper

    projet = tmp_path / "p"
    creer(projet, auteur="Ada")
    rattraper(projet, 1, set())

    assert (
        git(projet, "log", "-1", "--format=%s").stdout.strip()
        == "chore(course): use reference solution for chapter 1"
    )
    assert git(projet, "status", "--porcelain").stdout == ""
```

(The parametrized test is the slowest of the suite; keep `delai=120`.)

- [ ] **Step 2: Run** — Expected: FAIL (modules absent).
- [ ] **Step 3: Implement.** If a skeleton makes its corrector crash (message « planté »), fix the corrector or the skeleton so the failure is a clear expected/observed message.
- [ ] **Step 4: Run** full validation + gate.
- [ ] **Step 5: Commit** `feat(course): verify a chapter inside the learner project and catch up from the reference`.

### Task 5: Moteur terminal branché sur le projet

**Files:**
- Modify: `cours.py`, `README.md`, `pyproject.toml` (`extend-exclude` : drop `.solutions`, `atelier`), `.gitignore` (drop `.solutions/`, `atelier/`)
- Test: `tests/test_parcours.py`

**Interfaces:**
- Consumes: everything above.
- Produces: CLI `python3 cours.py [N] [--nouveau DOSSIER] [--projet DOSSIER] [--rattraper N] [--publier] [--env] [--reset]`; progression `.progression.json` = `{"projet": str|None, "lus": [], "quiz": {}, "katas": [], "rattrapes": []}`; `faits(prog) -> set[int]` = katas ∪ rattrapes.

Behaviour :
- `--nouveau DOSSIER` : `creer(DOSSIER, auteur=git config user.name or getpass.getuser())`, stores the absolute path in `projet`, prints next steps.
- `--projet DOSSIER` : stores an existing project path (must contain `fabrique/modeles.py` and `.git`).
- Opening an atelier without a project : explains `--nouveau` and returns.
- Opening chapter N whose earlier chapters are not all in `faits` : lists them and offers, per chapter, `rattraper` (o/N).
- Atelier : prints the file path inside the project and the installed test files; keys `[v]érifier [i]ndice [s]olution [t]uteur [q]uitter` (`[t]` prints « le tuteur arrive au plan D » until plan D replaces it — plan D owns this key). `[v]` → `verifier` → prints each line (vert `ok` / rouge `échec`) and the tail of the pytest output on failure; on success marks the kata done and asks « commiter ton travail ? (o/N) », then `commiter(projet, [module, *tests], kata.message_commit)`. `[i]` shows the next hint of `kata.indices` (graded, one more per press). `[s]` asks confirmation, then prints the reference module from `racine`. No `[r]` key (the learner uses `git checkout -- <fichier>`; the atelier prints that command once).
- `--rattraper N` : `rattraper` + records N in `rattrapes`.
- `--publier` : Task 6.
- Remove `ranger_module`, `restaurer_module`, `restaurer_tout`, `charger_module`, `charger_pointe`, `ATELIER`, `SOLUTIONS`, `--restaurer`. Docstring no longer claims « aucune dépendance » (the course needs the venv).
- `README.md` : replace the atelier/`.solutions` mechanics with the new flow (`--nouveau`, atelier, commit, `--rattraper`, `--publier`), and the chapter table with the new order.

- [ ] **Step 1: Write the failing tests** for the pure helpers moved out of the interactive loop (put them in `cours.py`, importable) :

```python
def test_faits_reunit_ateliers_valides_et_rattrapages():
    import cours

    assert cours.faits({"katas": [1, 3], "rattrapes": [2]}) == {1, 2, 3}


def test_chapitres_manquants_avant_un_atelier():
    import cours

    assert cours.manquants(5, {1, 2, 4}) == [3]


def test_le_moteur_n_echange_plus_de_modules():
    import cours

    for nom in ("ranger_module", "restaurer_module", "restaurer_tout", "SOLUTIONS"):
        assert not hasattr(cours, nom), nom
```

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.** Then drive the real CLI once by hand in a scratch directory with piped input and record the transcript in the report: `printf '' | .venv/bin/python cours.py --nouveau /tmp/.../p`, `.venv/bin/python cours.py --rattraper 1`, `printf 'v\no\nq\n' | .venv/bin/python cours.py 2` after writing a correct validator by copying the reference (to see the success + commit path), `git -C /tmp/.../p log --oneline`. Use a scratch HOME-independent progression by setting `COURS_PROGRESSION=<scratch>/prog.json` (add this env override for the progression path; tests use it too).
- [ ] **Step 4: Run** full validation + gate.
- [ ] **Step 5: Commit** `feat(course): drive workshops inside the learner project`.

### Task 6: Publication et test de bout en bout

**Files:**
- Create: `parcours/publication.py`
- Modify: `cours.py` (`--publier`), `.github/workflows/ci.yml` (git identity env for tests), `README.md`
- Test: `tests/test_parcours.py`

**Interfaces:**
- Produces :

```python
@dataclass(frozen=True)
class Controle:
    nom: str
    ok: bool
    detail: str

def controler(projet: Path, faits: set[int]) -> list[Controle]
def commande_publication(projet: Path) -> str
def brouillon_de_post(projet: Path, rattrapes: set[int]) -> str
```

`controler` checks, in order: all chapters 1–12 in `faits`; `git status --porcelain` empty; `ruff check .`; `ruff format --check .`; `pytest -q -p no:cacheprovider`; `python -m fabrique.evaluation.ci` — each in the project with `PYTHONPATH=projet`, env as in `verifier`. `commande_publication` returns `gh repo create <nom-du-dossier> --public --source <projet> --remote origin --push` (flags from `gh repo create --help`, gh 2.96.0). `brouillon_de_post` returns a short French post draft describing what the project does (graph, guardrails, MCP pricing, fallback under budget, human review, traces, CI gate), the stack, the link placeholder `<lien du dépôt>`, and, if `rattrapes` is not empty, an honest line listing the chapters taken from the reference solution. `cours.py --publier` prints the controls; if all pass, prints the command and the draft, and never runs `gh` itself.

- [ ] **Step 1: Write the failing tests** :

```python
def test_un_projet_complet_passe_tous_les_controles_de_publication(tmp_path, env_git):
    from parcours.projet import creer, rattraper
    from parcours.publication import commande_publication, controler

    projet = tmp_path / "ma-fabrique"
    creer(projet, auteur="Ada")
    faits = set()
    for n in range(1, 13):
        rattraper(projet, n, faits)
        faits.add(n)

    controles = controler(projet, faits)

    assert all(c.ok for c in controles), [(c.nom, c.detail[-2000:]) for c in controles if not c.ok]
    assert (projet / ".github/workflows/ci.yml").is_file()
    assert (
        commande_publication(projet)
        == f"gh repo create ma-fabrique --public --source {projet} --remote origin --push"
    )


def test_un_projet_incomplet_ne_se_publie_pas(tmp_path, env_git):
    from parcours.projet import creer
    from parcours.publication import controler

    projet = tmp_path / "p"
    creer(projet, auteur="Ada")

    premier = controler(projet, set())[0]
    assert not premier.ok and "1" in premier.detail


def test_le_brouillon_avoue_les_rattrapages(tmp_path):
    from parcours.publication import brouillon_de_post

    assert "4" in brouillon_de_post(tmp_path, {4})
    assert "rattrap" not in brouillon_de_post(tmp_path, set()).lower()
```

- [ ] **Step 2: Run** — Expected: FAIL.
- [ ] **Step 3: Implement.** In `.github/workflows/ci.yml`, add the four `GIT_*` identity variables at job level (`env:`), citing https://docs.github.com/en/actions/writing-workflows/workflow-syntax-for-github-actions#jobsjob_idenv in the commit body after reading it.
- [ ] **Step 4: Run** full validation + gate; report the duration of `tests/test_parcours.py`.
- [ ] **Step 5: Commit** `feat(course): check and prepare the learner's project for publication`.
