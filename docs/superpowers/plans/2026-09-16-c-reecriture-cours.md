# C — Réécriture pédagogique du cours : implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Chaque chapitre enseigne tout ce que son atelier exige, dans une structure qui suit la recherche (prédire, exemple résolu, atelier guidé puis de moins en moins, rappel espacé), en français correct et accentué.

**Architecture:** Contenu seulement : `contenu/chNN.py` (blocs, prédictions, questions, indices gradués, notes tuteur, à retenir, sources) et l'affichage correspondant dans `cours.py`. Les squelettes et correcteurs viennent du plan B et ne changent que si un texte révèle une incohérence.

**Tech Stack:** `modele.py` (Chapitre, Bloc, Question, Kata, Source), `cours.py`.

**Spec:** `docs/superpowers/specs/2026-09-16-parcours-apprenant-design.md` (section 2, « Structure d'un chapitre »).

## Global Constraints

- Structure de chaque chapitre, dans cet ordre :
  1. `objectif` et un premier bloc « Où on en est » : le schéma du flux de l'application avec le module du chapitre repéré (`[ICI]`), et ce qui est déjà écrit.
  2. `predictions` : 1 ou 2 questions sur un extrait de code ou un scénario, posées AVANT la leçon (PRIMM). L'explication est affichée après la réponse.
  3. Leçon : concept, un exemple résolu complet sur un problème voisin (jamais le code de l'atelier), les pièges. Chaque notion utilisée par l'atelier ou par son correcteur est enseignée ici ou dans un chapitre antérieur, avec son API exacte.
  4. Atelier : `consigne` qui dit quoi écrire, où (chemin dans le projet), quels tests vont tourner ; `indices` : 3 niveaux, du plus vague (concept) au plus précis (démarche), jamais la solution complète ; `notes_tuteur` : approche attendue, pièges fréquents, concepts en jeu, en prose, sans code.
  5. `questions` : 3 ou 4, dont 1 ou 2 sur des chapitres antérieurs (rappel espacé), au moins une de type `"ordre"` dans les chapitres 1, 4, 6, 7, 12 (remettre dans l'ordre des étapes ou des nœuds, avec un élément piège dans `options` absent de `bonne`).
  6. `a_retenir` : 3 à 5 questions d'explication (« sais-tu expliquer pourquoi… »).
  7. `sources` : chaque affirmation technique a une source avec son niveau (`doc`, `recherche`, `execute`, `auteur`). Toute API citée est vérifiée dans la version installée (`.venv/lib/python3.12/site-packages/...`) ou dans la doc officielle ; la source est citée.
- Longueur : 25 à 45 minutes de lecture et d'atelier. Pas de remplissage.
- Français correct et accentué dans tout texte affiché (y compris `cours.py`). Identifiants et code en ASCII, conformes au code réel de `fabrique/`.
- Ton : tutoiement, phrases courtes, exemples concrets tirés de l'hébergeur fictif du catalogue.
- Le texte ne parle plus d'échange de modules ni de `.solutions` ; il parle du projet de l'apprenant.
- Tests existants verts : `tests/test_parcours.py` (squelettes, correcteurs), toute la suite, ruff, porte.
- Commits : `docs(course): rewrite chapter N — <titre>` + `Co-Authored-By: Claude <noreply@anthropic.com>`.
- Branche : `feat/course-rewrite`, créée depuis `feat/learner-project`.

## Contenu attendu par chapitre

| # | Titre | Ce que la leçon doit enseigner (en plus de la structure) | Prédiction | Exemple résolu (voisin) |
|---|---|---|---|---|
| 0 | La fabrique en marche | Le problème (pages web générées, prix en dur interdits), le flux complet, les 12 étapes du parcours, comment se passe un atelier, `--nouveau`, le tuteur et son consentement, `--rattraper`, `--publier`. Démo : `python3 cours.py --demo` exécute le graphe de référence avec le fournisseur factice sur une page à tableau de prix et affiche le journal (rédaction, contrôle, correction, tarification, validation humaine simulée, publication). | « Que fait le graphe d'une page qui contient deux titres ? » | — |
| 1 | Contrats Pydantic et réparation | `BaseModel`, `Field`, `model_validate_json`, `ValidationError.errors()` et `loc`, boucle bornée, pourquoi réinjecter l'erreur, `SortieInvalide`, le contrat `Fournisseur.generer(retour=...)`, `FournisseurFake` scripté | Que renvoie `errors()` pour un champ trop long ? | réparer une `Adresse` |
| 2 | Garde-fous déterministes | grille déterministe/outil/dataset/juge, `Violation`, gravité, indice actionnable, regex (`re.compile`, groupes non capturants, `\b`, `IGNORECASE`), `BlocPage.type` et `product_ref`, pourquoi les prix sont interdits dans `contenu` | Laquelle de ces chaînes le motif attrape-t-il ? | valider une fiche produit |
| 3 | Un vrai serveur MCP | modèle hôte/client/serveur, `MCPServer`, `@tool`, descriptions pour le modèle (quand utiliser, quand ne pas utiliser), schémas d'entrée, `ToolError` contre plantage, `Client(serveur)` en mémoire, `call_tool` et `structured_content` | Que voit le client quand l'outil lève `ValueError` ? | un serveur de météo |
| 4 | Erreurs, repli et budget | taxonomie `Surcharge`/`SortieInvalide`/`Fatale`/`BudgetDepasse`, une stratégie par catégorie, enveloppe débitée avant l'essai, `Resultat` qui nomme le fournisseur, `chaine_depuis_reglages`, pourquoi pas de backoff ici (le retry vit au niveau du graphe), coûts réels des modèles | Ordre des appels pour une chaîne [surchargé, invalide puis valide] | un repli de géocodage |
| 5 | Contexte sous budget | budget de tokens, estimation, messages système conservés, garder les plus récents, résumer les écartés, `trim_messages` et pourquoi on ne l'utilise pas ici, où c'est utilisé (invite de rédaction) | Quels messages restent pour un budget de 20 ? | compacter un historique de support |
| 6 | Le graphe LangGraph | `StateGraph`, état `TypedDict`, réducteurs (`Annotated[list, fn]`), nœuds, arêtes conditionnelles et `path_map`, `RetryPolicy`, `checkpointer` et `thread_id`, composition à la racine et injection, tarification par MCP ; `interrupt()` présenté comme boîte noire fournie (détaillé au chapitre 7) | Ordre des nœuds pour une page invalide puis valide | un graphe de modération de commentaire |
| 7 | Validation humaine | `interrupt()`, rejeu du nœud à la reprise, `Command(resume=...)`, `get_state().next`, pourquoi la publication vit dans un nœud séparé, idempotence | Combien de fois s'exécute le code avant `interrupt()` ? | validation d'un remboursement |
| 8 | API et persistance | FastAPI, modèles de requête/réponse, codes 202/402/404/409/422/502/503, routes `def` et pool de threads, `lifespan`, `InMemorySaver` contre `PostgresSaver`, `TestClient`, lancer `uvicorn` et `docker compose` pour de vrai | Quel code HTTP pour une validation sur un thread déjà publié ? | une API de tickets |
| 9 | Observabilité | traces, spans, générations, scores, `observation()`, graine de trace par `thread_id`, garde `actif()` et variables vides, exporteur OpenTelemetry en mémoire pour tester, ce qu'on regarde pour diagnostiquer une régression | Combien de traces pour une page validée après reprise ? | tracer un appel de traduction |
| 10 | Évaluation | golden dataset, évaluateurs purs, moyennes, `Evaluation`, `RegressionError`, `lancer_local`, marge, ce que l'évaluation avec le fournisseur factice protège et ne protège pas | Que renvoie le verdict pour une moyenne de 0,94 contre 1,0 et une marge de 0,05 ? | évaluer un résumeur |
| 11 | Porte de non-régression et CI | `argparse`, codes de sortie, référence versionnée, `--ecrire-reference` comme geste relu, GitHub Actions (déclencheurs, jobs, étapes, versions épinglées), le workflow installé dans le projet, `ruff` | Que fait la CI si `reference.json` est absent ? | une porte de performance |
| 12 | Temporal | workflow déterministe, activités, `execute_activity`, `start_to_close_timeout`, `RetryPolicy`, `workflow.now()`/`workflow.uuid4()`, appels interdits, idempotence de publication, `WorkflowEnvironment` pour tester, quand choisir Temporal plutôt que LangGraph | Lequel de ces appels casse le rejeu ? | un workflow d'inscription |

`--demo` (chapitre 0) est une nouvelle option de `cours.py` : elle construit le graphe de référence avec `FournisseurFake(reponses=[page à deux titres, page valide à tableau de prix vps-comfort])`, `InMemorySaver`, invoque, affiche le journal et le prix résolu, reprend avec approbation, affiche la publication. Un test l'exécute.

---

### Task 1: Affichage des prédictions, des questions « ordre » et des indices gradués

**Files:**
- Modify: `cours.py`, `contenu/ch00.py`
- Test: `tests/test_parcours.py`

**Interfaces:**
- Produces: `cours.jouer_predictions(ch, prog)`, `cours.corriger(question, reponse: str) -> bool` (pure : `"b"` pour un choix, `"cab"` pour un ordre), `cours.demo() -> list[str]` (renvoie les lignes affichées), option `--demo`.

- [ ] **Step 1: Write the failing tests** :

```python
def test_corriger_un_choix_et_un_ordre():
    import cours
    from modele import Question

    choix = Question(enonce="?", options=["a", "b"], bonne=1, explication="")
    ordre = Question(
        enonce="?", options=["x", "y", "z", "piege"], bonne=[2, 0, 1], explication="", kind="ordre"
    )

    assert cours.corriger(choix, "b", ordre_affiche=[0, 1])
    assert not cours.corriger(choix, "a", ordre_affiche=[0, 1])
    assert cours.corriger(ordre, "cab", ordre_affiche=[0, 1, 2, 3])
    assert not cours.corriger(ordre, "cabd", ordre_affiche=[0, 1, 2, 3])


def test_la_demo_montre_correction_tarification_et_publication():
    import cours

    lignes = "\n".join(cours.demo())
    for attendu in ("correction", "tarification", "7.99 EUR / mois", "publication"):
        assert attendu in lignes
```

(`ordre_affiche` maps displayed letters to option indexes, since options are shuffled.)

- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** ; the chapter flow becomes : prédictions → leçon → atelier → quiz → à retenir → sources.
- [ ] **Step 4: Run** full validation ; drive `python3 cours.py --demo` and record output.
- [ ] **Step 5: Commit** `feat(course): add predictions, ordering questions, graded hints and a demo`.

### Tasks 2 to 14: Réécrire le chapitre N (N = 0 … 12)

One task per chapter, same shape. **Files:** `contenu/chNN.py` (texte, prédictions, questions, indices, notes tuteur, à retenir, sources) ; squelette et correcteur seulement si le texte révèle une incohérence (then `tests/test_parcours.py` must stay green).

- [ ] **Step 1:** Lire le module de référence du chapitre, son squelette, son correcteur, ses fichiers de tests, et le chapitre actuel.
- [ ] **Step 2:** Vérifier chaque API citée dans la version installée ou la doc officielle ; noter chaque source avec son niveau.
- [ ] **Step 3:** Réécrire le chapitre selon les Global Constraints et la ligne du tableau.
- [ ] **Step 4:** Lancer `.venv/bin/python -c "from contenu import CHAPITRES; ch = CHAPITRES[N]; print(len(ch.predictions), len(ch.questions), len(ch.kata.indices) if ch.kata else '-')"`, puis `printf '\n%.0s' {1..200} | .venv/bin/python cours.py N` n'est pas utilisable (lecture interactive) : à la place, appeler `cours.jouer_lecon(ch)` dans un script qui remplace `input` par une fonction qui renvoie `""`, et relire la sortie complète affichée. Validation complète.
- [ ] **Step 5: Commit** `docs(course): rewrite chapter N — <titre>`.

Add to `tests/test_parcours.py` in Task 2 (chapter 0), so every later chapter is held to it :

```python
@pytest.mark.parametrize("chapitre", CHAPITRES, ids=lambda c: f"ch{c.numero:02d}")
def test_structure_pedagogique(chapitre):
    assert 1 <= len(chapitre.predictions) <= 2
    assert 3 <= len(chapitre.questions) <= 4
    assert 3 <= len(chapitre.a_retenir) <= 5
    assert chapitre.sources
    if chapitre.kata:
        assert len(chapitre.kata.indices) == 3
        assert chapitre.kata.notes_tuteur
        assert "NotImplementedError" not in chapitre.kata.notes_tuteur
    for question in chapitre.predictions + chapitre.questions:
        if question.kind == "ordre":
            assert isinstance(question.bonne, list) and len(question.bonne) < len(question.options)


def test_le_texte_affiche_est_accentue():
    import re

    mots_sans_accent = re.compile(
        r"\b(deja|etre|probleme|reponse|verifie|genere|modele|donnees|resume|systeme|premiere|derniere|methode|regle|reessai)\b"
    )
    for chapitre in CHAPITRES:
        textes = [b.contenu for b in chapitre.blocs if b.kind != "code"]
        textes += [chapitre.titre, chapitre.objectif, *chapitre.a_retenir]
        for q in chapitre.predictions + chapitre.questions:
            textes += [q.enonce, q.explication, *q.options]
        if chapitre.kata:
            textes += [chapitre.kata.consigne, *chapitre.kata.indices]
        fautes = sorted({m for t in textes for m in mots_sans_accent.findall(t)})
        assert not fautes, (chapitre.numero, fautes)
```

The structure test is marked `xfail(strict=False)` for chapters not yet rewritten only if needed to keep the suite green between tasks ; remove every xfail in the last task (chapter 12).
