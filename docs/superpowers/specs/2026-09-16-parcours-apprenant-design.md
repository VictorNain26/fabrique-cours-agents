# Parcours apprenant : projet personnel, pédagogie, tuteur

Date : 2026-09-16. Statut : validé par délégation (« je te laisse faire les choix
qui vont dans le bon sens »).

## But

Ce dépôt est **le cours** : moteur (`cours.py`), leçons (`contenu/`), application
de référence (`fabrique/`) et ses tests. L'apprenant, lui, construit **son propre
projet** au fil des leçons, dans un dossier à lui, qu'il pousse sur son GitHub à
la fin comme projet personnel à montrer. Son dépôt ne contient aucun contenu de
cours : un README de projet, son code, ses tests, sa CI.

Aujourd'hui, l'atelier écrase un module suivi par git puis le restaure avec la
solution : l'apprenant perd son code et ne repart avec rien.

## Décisions

| Sujet | Décision | Raison |
|---|---|---|
| Où vit le code de l'apprenant | Un projet généré par `cours.py nouveau DOSSIER`, dépôt git indépendant | Pas de second dépôt template à maintenir ; le cours reste la seule source |
| Solutions | Restent dans ce dépôt (public) ; jamais copiées dans le projet sauf rattrapage explicite | Le projet montré doit être le code de l'apprenant |
| Couplage entre chapitres | Ordre qui suit le graphe d'imports + composition à la racine + squelettes importables | Un chapitre n'importe que des modules déjà écrits ou fournis |
| Blocage | `cours.py --rattraper N` copie le module de référence et le commit sous un message explicite | Filet de sécurité visible dans `git log` |
| Tests | Une seule suite, dans ce dépôt ; chaque fichier déclare ses chapitres ; copiée dans le projet à l'ouverture de l'atelier | Le test est la spécification ; correcteur local et CI du projet lancent les mêmes tests |
| Vérification | Sous-processus, `cwd` = projet, projet en tête de `sys.path` | Le paquet `fabrique` du projet masque celui de la référence |
| Fil rouge MCP | Branché réellement : nœud `tarification` qui résout les prix via le serveur MCP | Le README promet ce que le code fait |
| Contexte | `compacter` utilisé par la rédaction pour borner l'historique des retours | Le chapitre construit un module utilisé |
| Tuteur | Dans le cours (`tuteur/`), un seul appel LLM, indices gradués décidés par le code, garde-fou anti-code | Recherche : Bastani 2025, Kestin 2025, CodeHelp 2023, Anthropic « Building effective agents » |
| Chapitre bonus tuteur | Non | Le tuteur n'appartient pas au projet de l'apprenant |
| `[s]olution` | Conservé, affiche le module de référence après confirmation | La solution est publique ; le rattrapage est l'action qui l'installe |
| Ordre des fournisseurs du tuteur | Celui de `FOURNISSEURS` ; jeu d'évaluation fourni pour trancher avec de vraies clés | Pas de choix a priori sans mesure |
| Publication | `cours.py --publier` vérifie tout puis affiche la commande `gh repo create` et un brouillon de post | L'apprenant garde la main sur son compte |

## 1. Application de référence (`fabrique/`)

### Corrections

- **Budget réel** : `cout_par_appel` n'est jamais passé, il vaut 0.0 et le 402 ne
  se déclenche pas. `Reglages` gagne `cout_estime_ovhcloud` et
  `cout_estime_anthropic` (enveloppe estimée par appel, en euros). Une seule
  fabrique `fabrique/providers/chaine.py:chaine_depuis_reglages()` remplace les
  copies de `api.py` et `temporal/activites.py`.
- **Modèle Anthropic** : `FournisseurAnthropic.modele` devient obligatoire ; le
  défaut vit dans `Reglages` seulement.
- **API** : les routes deviennent `def`. FastAPI les exécute dans un pool de
  threads (https://fastapi.tiangolo.com/async, « Path operation functions ») :
  `graphe.invoke` ne bloque plus la boucle, et un nœud peut lancer
  `asyncio.run` pour appeler MCP.

### Composition à la racine

```python
def construire(
    fournisseurs, pages_existantes, *,
    checkpointer=None, max_tours=3, budget_par_page=0.50,
    budget_tokens_invite=1500,
    publier=_publier_neutre,
    valider=validateur.valider,
    generer=reparation.generer_valide,
    repli=repli.executer,
    compacter=contexte.compacter,
    resoudre_prix=client_catalogue.resoudre_prix,
) -> CompiledStateGraph
```

Les appelants existants ne changent pas. Les tests du graphe injectent des
doubles et ne dépendent plus du code des autres chapitres.

### Flux

```
redaction -> controle -> [correction -> redaction]* -> tarification
          -> [correction -> redaction]* -> validation_humaine -> publication
```

- **redaction** : invite = brief + retours de correction, compactés sous
  `budget_tokens_invite` par `compacter` (résumé déterministe des retours
  écartés : codes et indices). L'état gagne `retours: list[str]` (réducteur de
  concaténation) ; `Overwrite` disparaît.
- **tarification** : pour chaque bloc `tableau_prix`, appelle
  `resoudre_prix(reference)` ; renseigne `BlocPage.prix_affiche` (nouveau champ,
  hors `contenu`, donc hors garde-fou prix). Référence inconnue : violation
  bloquante `REF_PRODUIT_INCONNUE` et retour en correction, borné par
  `max_tours`.
- **`fabrique/mcp_catalogue/client.py`** : `resoudre_prix(reference)` ouvre
  `mcp.Client(construire())` en mémoire et appelle l'outil `resoudre_prix`.
  Source : docstring de `mcp.Client` (mcp 2.2.0 installé) : « in tests - a
  `Server` or `MCPServer` instance to connect to it in-process ».
- **Évaluateur** `refs_produit_resolues` : compare `prix_affiche` au catalogue.
- La référence `reference.json` est régénérée volontairement, diff relu.

### Observabilité

`observation()` accepte `trace=` (défaut `"page"`), pour que le tuteur ouvre des
traces `tuteur`.

## 2. Nouveau parcours

Ordre compatible avec les imports, précédé d'une vue d'ensemble :

| # | Chapitre | Module écrit | Importe (déjà écrit ou fourni) |
|---|---|---|---|
| 0 | La fabrique en marche | — (démo, création du projet) | — |
| 1 | Contrats Pydantic et réparation | `generation/reparation.py` | fourni |
| 2 | Garde-fous déterministes | `garde_fous/validateur.py` | fourni |
| 3 | Un vrai serveur MCP | `mcp_catalogue/serveur.py` | fourni (catalogue, client) |
| 4 | Erreurs, repli et budget | `providers/repli.py` | fourni |
| 5 | Contexte sous budget | `generation/contexte.py` | — |
| 6 | Le graphe LangGraph | `generation/graphe.py` | 1 à 5 |
| 7 | Validation humaine | `generation/reprise.py` | 6 (tests : graphe minimal) |
| 8 | API et persistance | `api.py` | 6, 7 |
| 9 | Observabilité | `observabilite.py` (branche Langfuse) | fourni |
| 10 | Évaluation | `evaluation/experience.py` | 2 |
| 11 | Porte de non-régression et CI | `evaluation/ci.py` + workflow | 6, 10 |
| 12 | Temporal | `temporal/workflows.py` | 1, 2, 4 via activités |

L'application tourne pour de vrai dès le chapitre 8 (`uvicorn`, `curl`), et la
démo du chapitre 0 la montre entière avant toute ligne de code (approche « whole
game », 4C/ID).

**Fournis dans le projet dès sa création** : `modeles.py`, `config.py`,
`providers/{base,fake,ovhcloud,anthropic,chaine}.py`, `mcp_catalogue/catalogue.py`,
`mcp_catalogue/client.py`, `evaluation/{dataset,evaluateurs}.py`,
`temporal/{activites,worker}.py`, `observabilite.py` avec sa branche inactive
écrite (le chapitre 9 fait écrire la branche Langfuse), Dockerfile, compose,
`.env.exemple`, `pyproject.toml`, `requirements*.txt`, README de projet,
`.gitignore`. Le workflow GitHub Actions arrive au chapitre 11.

**Squelettes** : chaque module de chapitre existe dès la création, importable,
ruff-propre, tous ses noms publics présents, `NotImplementedError("chapitre N")`
à l'appel. Aide dégressive : les premiers chapitres laissent peu à écrire, les
derniers presque tout.

### Structure d'un chapitre

1. **Objectif et place dans l'app** : quel nœud ou module, schéma du flux.
2. **Prédire** (PRIMM) : 1 à 2 questions sur un extrait, avant la leçon.
3. **Leçon** : concept, exemple résolu complet sur un problème voisin (pas la
   solution de l'atelier), pièges.
4. **Atelier** : consigne, tests comme spécification, indices gradués
   (`Kata.indices`, du plus vague au plus précis), tuteur.
5. **Quiz de rappel** : 3 à 4 questions, dont 1 à 2 sur des chapitres
   antérieurs ; format « remettre dans l'ordre » (Parsons) disponible.
6. **Ce que tu dois savoir expliquer**, **sources** avec niveau de preuve.

Écriture : français accentué dans tout le texte affiché ; identifiants de code
en ASCII ; chaque notion exigée par un atelier est enseignée avant.

## 3. Moteur du cours (`cours.py`)

- `nouveau DOSSIER` : génère le projet, `git init`, commit
  `chore: scaffold project`, retient le chemin dans `.progression.json`.
- Atelier : copie dans le projet les fichiers de tests dont tous les chapitres
  sont faits ou en cours ; `[v]` lance, en sous-processus dans le projet, le
  correcteur `verifN` puis `pytest` sur ces fichiers ; validé → proposition de
  commit (fichier par fichier) avec un message conventionnel propre au chapitre.
- `[r]` demande confirmation. Plus d'échange de modules, plus de `.solutions/`,
  plus de `--restaurer`.
- `--rattraper N` : copie module et tests de référence, commit
  `chore(course): use reference solution for chapter N`, marque le chapitre
  rattrapé.
- `--publier` : exige tous les chapitres faits ou rattrapés, lance dans le projet
  `ruff check`, `ruff format --check`, `pytest`, la porte ; affiche la commande
  `gh repo create <nom> --public --source . --push` et un brouillon de post.
- Nouveaux types dans `modele.py` : `Chapitre.predictions`, `Question.kind`
  (`"choix"` | `"ordre"`), `Kata.indices`, `Kata.notes_tuteur`,
  `Kata.tests`, `Kata.message_commit`.

## 4. Tuteur (`tuteur/`, dans le cours)

- Touche `[t]` dans l'atelier. Désactivé si la chaîne ne contient que `fake`.
- Consentement explicite au premier usage, qui nomme les fournisseurs et
  Langfuse ; mémorisé dans `.progression.json`.
- Contexte d'un seul appel : consigne, `notes_tuteur`, fichier de l'apprenant
  encodé en JSON et déclaré comme donnée, échecs du correcteur, indices déjà
  donnés, niveau autorisé.
- Niveaux : 1 quelle vérification échoue et quel concept ; 2 où regarder ;
  3 stratégie en prose ; 4 indice statique du chapitre. Le niveau suivant
  n'est débloqué qu'après un nouvel essai `[v]` en échec.
- Garde-fou : schéma `Indice` dont le validateur refuse les blocs de code, les
  lignes qui se lisent comme du Python et les textes trop longs ; le refus
  devient `SortieInvalide`, que `executer` réessaie puis bascule.
- Quota : 10 indices par session, un regagné toutes les 3 minutes (CS50.ai).
- Trace Langfuse `tuteur` si les clés sont présentes.
- Évaluation : cas bloqués générés par mutation des solutions, règles
  déterministes (pas de code, pas de fuite par similarité avec la référence,
  mention de la vérification en échec) ; lancée à la main avec de vraies clés.
  La CI ne teste que la plomberie avec le fournisseur factice.

## 5. Tests de ce dépôt

- Suite existante adaptée : marqueur `chapitres(...)` par fichier, injection de
  doubles dans les tests du graphe.
- `tests/test_parcours.py` :
  - chaque squelette est importable, ruff-propre, expose les noms et signatures
    du module de référence ;
  - chaque `verifN` échoue proprement (sans exception ni blocage) sur le
    squelette et passe sur la référence ;
  - un projet généré passe sa suite initiale ;
  - un projet dont tous les chapitres sont rattrapés passe `pytest`, ruff et la
    porte, soit exactement ce que `--publier` exige.
- `tests/test_tuteur.py` : contexte, niveaux, rejet du code, consentement,
  quota, sans réseau.

## Hors périmètre

Déploiement sur une infrastructure réelle ; appels payants en CI ; interface
web du cours.

## Livraison

Branches empilées, une PR chacune : spec → application de référence → projet
apprenant et moteur → réécriture du cours → tuteur. Merge après accord.
