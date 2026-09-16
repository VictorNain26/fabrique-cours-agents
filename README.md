# La fabrique — cours interactif et application

Un cours en terminal dont les ateliers **sont** les modules d'une application qui
tourne. À la fin des douze chapitres, tu n'as pas douze fichiers d'exercice : tu as
un service de génération de pages web sous garde-fous, avec validation humaine,
persistance, observabilité et une porte de non-régression en intégration continue.

Un cours pour apprendre à construire des agents IA qui tiennent en production,
dont les ateliers écrivent les modules d'une application réelle.

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
`product_ref`, jamais un prix, et le prix réel est résolu par un serveur MCP qui
interroge le catalogue. Le chapitre 5 et le chapitre 6 cessent d'être deux
exercices séparés.

```
brief -> redaction -> controle -> [correction -> redaction]* -> tarification -> [correction -> redaction]* -> validation humaine -> publication
            |             |                          |                                     |
    chaine de repli   garde-fous              client MCP catalogue                     interrupt()
```

`tarification` résout, pour chaque `tableau_prix`, le prix réel via un client
MCP connecté en mémoire au serveur du catalogue, et l'écrit dans
`prix_affiche` — un champ retiré du schéma JSON envoyé au modèle
(`SkipJsonSchema`) et systématiquement écrasé par le nœud, même si le modèle en
a inventé un. Une référence absente du catalogue lève une violation bloquante
`REF_PRODUIT_INCONNUE` et repart en correction ; un crash réel du catalogue,
lui, remonte comme une erreur, pas comme une référence inconnue.

Les retours de correction ne remplacent plus le tour précédent : ils
s'accumulent dans l'état et sont compactés sous un budget de tokens
(`BUDGET_TOKENS_INVITE`) avant chaque rédaction, par la fonction `compacter` du
chapitre 3.

La rédaction passe par une **chaîne de fournisseurs** ordonnée du moins cher au
plus cher : le premier qui répond gagne, on ne bascule que sur surcharge, et le
nom de celui qui a réellement répondu est écrit dans l'état avec son coût.
Chaque essai débite d'abord une enveloppe de coût estimé du budget restant,
avant même l'appel réseau — épuisée, l'API renvoie 402. Un nom absent de
`fake`, `ovhcloud`, `anthropic` dans `FOURNISSEURS` est rejeté au démarrage.

```
FOURNISSEURS=ovhcloud,anthropic   # defaut : fake seul, aucun appel reseau
BUDGET_PAR_PAGE=0.50
COUT_ESTIME_OVHCLOUD=0.002        # euros, debite avant chaque essai OVHcloud
COUT_ESTIME_ANTHROPIC=0.01        # euros, debite avant chaque essai Anthropic
```

Les modèles par défaut sont les moins chers de chaque fournisseur — Llama 3.3 70B
chez OVHcloud (0,67 €/M tokens), Haiku 4.5 chez Anthropic. C'est un cours et une
démonstration : mille pages coûtent environ un euro.

```bash
cp .env.exemple .env               # Postgres exige un mot de passe
docker compose up --build          # api sur http://localhost:8000
curl localhost:8000/sante
```

Quatre services, environ 460 Mo au total : l'API, Postgres, un **serveur Temporal
auto-hébergé** (MIT, pas Temporal Cloud) et le worker qui exécute les workflows.
L'API ne sert que le chemin LangGraph, avec validation humaine. Le workflow
Temporal du chapitre 4 (rédaction, contrôle, correction, publication, sans
validation humaine) partage les mêmes garde-fous et le même catalogue, mais
**aucune route ne le démarre** : il est exercé par `tests/test_temporal.py`, et le
worker du compose n'exécute que ce qu'on lui soumet à la main.

Les routes sont des fonctions `def` classiques, pas des coroutines : FastAPI
les exécute dans son pool de threads plutôt que sur la boucle asyncio
principale. C'est ce qui permet au nœud `tarification` d'appeler le client MCP
avec `asyncio.run()` sans lever d'erreur pour boucle déjà active.

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

## Observabilité

Avec `LANGFUSE_PUBLIC_KEY` et `LANGFUSE_SECRET_KEY`, chaque page devient **une
trace Langfuse**, dont l'identifiant est dérivé du `thread_id` : la reprise après
validation humaine retombe dans la même trace.

```
trace "page"
  redaction                  span : etat en entree, page + fournisseur + cout en sortie
    essai ovhcloud           span, ERROR sur Surcharge : le repli se lit dans la trace
      ovhcloud               generation : modele, tokens, cout_eur en metadonnee
    essai anthropic          span
      anthropic              generation : modele, tokens, cout en USD
  controle                   span
    LIEN_MORT                guardrail, avec un score booleen du meme nom
  correction                 span : le retour reinjecte a la redaction
  ...
  publication                span, apres la validation humaine : meme trace
```

Chaque appel fournisseur, factice compris, est une observation `generation`. Les
tokens sont notés dès la réponse, avant la validation du schéma : une sortie
invalide a déjà été facturée, elle doit compter. Le coût suit les tarifs
ci-dessous, sans en inventer :

- **Haiku 4.5** : `cost_details` en dollars, l'unité que Langfuse attend ;
- **OVHcloud** : facturé en euros, donc une métadonnée `cout_eur` plutôt qu'un
  taux de change inventé ;
- **tout autre modèle** : aucun coût déclaré, Langfuse le déduit de ses propres
  définitions de modèles s'il en a une.

Le budget du chapitre 8 ne change pas : `cout_par_appel` reste une enveloppe
débitée avant l'essai, la trace montre ce que l'appel a réellement consommé.
Pour diagnostiquer une régression, on filtre les traces `page`, on compare
tokens et latence par `generation`, et on repère les essais en `ERROR` et les
scores de garde-fous qui montent.

Sans clés, rien n'est ouvert. Des variables **présentes mais vides**, comme dans
`.env.exemple`, suffiraient pourtant au SDK pour démarrer un exportateur :
`fabrique.observabilite.actif()` coupe donc avant d'appeler le SDK.
`tests/test_observabilite_generations.py` lit les spans dans un exportateur
OpenTelemetry en mémoire, et
[`docs/langfuse.md`](docs/langfuse.md) explique comment brancher une instance.

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

La CI enchaîne les quatre sur un runner GitHub ; un run antérieur à ces
changements a mesuré 36 secondes. La porte de
non-régression rejoue le golden dataset, compare à
`fabrique/evaluation/reference.json` versionné dans le dépôt, et échoue si la
qualité recule au-delà de la marge. Une référence absente la fait échouer aussi ;
la créer ou la remplacer est un geste explicite,
`python -m fabrique.evaluation.ci --ecrire-reference`, dont le diff se relit en
revue.

## Les deux fournisseurs marchent contre leur API réelle

Pas seulement écrits contre la documentation : exécutés à la main, hors CI.

**OVHcloud AI Endpoints** (`Meta-Llama-3_3-70B-Instruct`) rend une `Page` valide
au premier essai grâce à `response_format`. **Anthropic** (`claude-sonnet-5`)
aussi, et la chaîne complète a été exercée de bout en bout : quand le modèle sort
du schéma, l'erreur nommant le champ lui repart et le second jet passe ; quand il
viole un garde-fou, la correction est réinjectée puis le graphe s'interrompt pour
la validation humaine et ne publie qu'une fois.

Haiku 4.5 est le modèle Anthropic par défaut, mais aucun appel à Haiku n'est
consigné : `tests/test_providers_reels.py` le cible, sans exécution enregistrée.
Son coût ci-dessous est une projection à partir du tarif publié ; celui d'OVHcloud
s'appuie sur les tokens d'un appel réel.

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
l'argent à chaque push finirait désactivée. La contrepartie : la porte de
non-régression protège la plomberie (graphe, garde-fous, boucle de réparation,
évaluateurs), **pas la qualité d'un vrai modèle**. Un changement de prompt ou de
modèle qui dégrade les pages réelles ne la fait pas échouer.

## Ce qui n'est pas couvert

Les tests automatisés ne couvrent les adaptateurs réels que sur la traduction de
leurs erreurs ; les appels ci-dessus ont été faits à la main, pas en CI. Les tests
d'intégration de `tests/test_providers_reels.py` sont ignorés par défaut.

Temporal n'est branché sur aucune route de l'API : le workflow n'est exercé que
par les tests et par soumission manuelle au worker.

Le chemin Temporal n'ouvre pas de trace de page : ses générations arrivent en
traces isolées, et le service `worker` du compose ne reçoit pas les clés
Langfuse.

Le déploiement sur une infrastructure réelle reste à faire : tout tourne en local
ou sur un runner GitHub.
