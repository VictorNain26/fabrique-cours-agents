# La fabrique — cours interactif et application

Un cours en terminal dont les ateliers **sont** les modules d'une application qui
tourne. À la fin des douze chapitres, tu n'as pas douze fichiers d'exercice : tu as
un service de génération de pages web sous garde-fous, avec validation humaine,
persistance, observabilité et une porte de non-régression en intégration continue.

Préparation entretien AI Website Factory (OVHcloud).

## Démarrer

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

python3 cours.py              # menu
python3 cours.py 5            # aller au chapitre 5
python3 cours.py --env        # comparer ton environnement aux versions de reference
python3 cours.py --restaurer   # remettre l'app en etat apres un atelier
python3 cours.py --reset      # effacer la progression
```

Python 3.10 ou plus. Aucune clé d'API n'est nécessaire : le fournisseur factice
fait tourner l'application, les tests et la CI.

## L'application

Un brief entre, une page validée sort. Le fil qui relie tous les chapitres : le
garde-fou **interdit les prix en dur**, donc le modèle doit émettre un
`product_ref`, et le prix réel est résolu par un serveur MCP qui interroge le
catalogue. Le chapitre 5 et le chapitre 6 cessent d'être deux exercices séparés.

```
brief -> redaction -> controle -> [correction -> redaction]* -> validation humaine -> publication
            |             |                                            |
    chaine de repli   garde-fous                                  interrupt()
```

La rédaction passe par une **chaîne de fournisseurs** ordonnée du moins cher au
plus cher : le premier qui répond gagne, on ne bascule que sur surcharge, et le
nom de celui qui a réellement répondu est écrit dans l'état avec son coût. Le
budget par page est vérifié avant chaque essai — dépassé, l'API renvoie 402.

```
FOURNISSEURS=ovhcloud,anthropic   # defaut : fake seul, aucun appel reseau
BUDGET_PAR_PAGE=0.50
```

Les modèles par défaut sont les moins chers de chaque fournisseur — Llama 3.3 70B
chez OVHcloud (0,67 €/M tokens), Haiku 4.5 chez Anthropic. C'est un cours et une
démonstration : mille pages coûtent environ un euro.

```bash
docker compose up --build          # api sur http://localhost:8000
curl localhost:8000/sante
```

Quatre services, environ 460 Mo au total : l'API, Postgres, un **serveur Temporal
auto-hébergé** (MIT, pas Temporal Cloud) et le worker qui exécute les workflows.
LangGraph orchestre le chemin avec validation humaine, Temporal le chemin
automatique et durable — les deux partagent les mêmes garde-fous et le même
catalogue.

| Route | Rôle |
|---|---|
| `POST /pages` | lance une génération, renvoie un `thread_id` et s'arrête pour validation |
| `GET /pages/{id}` | relit l'état courant |
| `POST /pages/{id}/validation` | approuve ou refuse ; publie une seule fois |
| `GET /sante` | sonde du conteneur |

## Les douze chapitres

| # | Chapitre | Module de l'app que tu écris |
|---|---|---|
| 1 | Pydantic v2 et réparation | `fabrique/generation/reparation.py` |
| 2 | LangGraph : le vrai StateGraph | `fabrique/generation/graphe.py` |
| 3 | Gestion du contexte | `fabrique/generation/contexte.py` |
| 4 | Temporal : le workflow déterministe | `fabrique/temporal/workflows.py` |
| 5 | Garde-fous déterministes | `fabrique/garde_fous/validateur.py` |
| 6 | MCP : un vrai serveur | `fabrique/mcp_catalogue/serveur.py` |
| 7 | Évaluation et non-régression | `fabrique/evaluation/experience.py` |
| 8 | Erreurs, retry, fallback et coûts | `fabrique/providers/repli.py` |
| 9 | Validation humaine | `fabrique/generation/reprise.py` |
| 10 | L'API et la persistance | `fabrique/api.py` |
| 11 | Observabilité | `fabrique/observabilite.py` |
| 12 | Livraison et non-régression | `fabrique/evaluation/ci.py` |

**Comment un atelier peut être un vrai module.** Ouvrir un atelier met le module de
l'app de côté dans `.solutions/` et installe le squelette à sa place. Le correcteur
teste **ce chemin-là**, pas une copie. À la sortie de l'atelier, le module est
restauré. `python3 cours.py --restaurer` rattrape une sortie brutale.

**Les douze chapitres sont adossés à un module réel, sans exception.** Le
correcteur du chapitre 4 introspecte les décorateurs du SDK Temporal puis analyse
l'arbre syntaxique de ta classe pour y traquer les appels non déterministes, et
ses tests exécutent de vrais workflows via `WorkflowEnvironment` — un serveur de
test embarqué dans le SDK, qui ne télécharge rien.

## Vérification

Chaque affirmation technique porte un niveau de preuve : `doc` (page officielle
lue), `recherche` (extrait), `execute` (comportement observé en lançant le code),
`auteur` (position, pas citation). Le détail est dans
[`docs/verification.md`](docs/verification.md), avec les URL.

```bash
pytest -q                            # la suite
ruff check . && ruff format --check .
python -m fabrique.evaluation.ci      # porte de non-regression
```

La CI enchaîne les quatre sur un runner GitHub, en 36 secondes. La porte de
non-régression rejoue le golden dataset, compare à
`fabrique/evaluation/reference.json` versionné dans le dépôt, et échoue si la
qualité recule au-delà de la marge.

## Les deux fournisseurs marchent contre leur API réelle

Pas seulement écrits contre la documentation : exécutés.

**OVHcloud AI Endpoints** (`Meta-Llama-3_3-70B-Instruct`) rend une `Page` valide
au premier essai grâce à `response_format`. **Anthropic** (`claude-sonnet-5`)
aussi, et la chaîne complète a été exercée de bout en bout : quand le modèle sort
du schéma, l'erreur nommant le champ lui repart et le second jet passe ; quand il
viole un garde-fou, la correction est réinjectée puis le graphe s'interrompt pour
la validation humaine et ne publie qu'une fois.

Haiku 4.5 est le modèle par défaut mais n'a pas été appelé : son tarif ci-dessous
est une projection, celui d'OVHcloud une mesure.

Le détail, avec un niveau de preuve par affirmation, est dans
[`docs/verification.md`](docs/verification.md).

## Ce que ça coûte

Tarifs relevés à la source : le catalogue OVHcloud annonce **0,67 € par million de
tokens**, entrée et sortie ; Haiku 4.5 est à 1 $/M en entrée et 5 $/M en sortie.

| | une page | 1 000 pages |
|---|---|---|
| OVHcloud Llama 70B | 0,0004 € | **1,09 €** |
| Anthropic Haiku 4.5 | 0,0055 € | 5,51 € |

**Les tests et la CI ne coûtent rien** : ils tournent sur le fournisseur factice,
zéro appel réseau. C'est délibéré — une porte de non-régression qui coûterait de
l'argent à chaque push finirait désactivée.

## Ce qui n'est pas couvert

Les tests automatisés ne couvrent les adaptateurs réels que sur la traduction de
leurs erreurs ; les appels ci-dessus ont été faits à la main, pas en CI.

Le déploiement sur une infrastructure réelle reste à faire : tout tourne en local
ou sur un runner GitHub.
