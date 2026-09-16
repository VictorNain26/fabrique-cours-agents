# Registre de vérification — 16/09/2026

Chaque affirmation technique du cours et de la fabrique est classée par niveau de
preuve. `execute` est le niveau le plus fort : le comportement a été observé en
lançant le code dans `.venv`.

## Versions, vérifiées par installation réelle

```
pydantic 2.13.5 · langgraph 1.2.11 · langgraph-checkpoint-postgres 3.1.2
langchain-core 1.6.3 · temporalio 1.33.0 · mcp 2.2.0 · langfuse 4.15.3
openai 3.14.0 · fastapi 0.141.1 · psycopg 3.3.5
```

## Faits établis par exécution

| Fait | Comment il a été établi |
|---|---|
| `mcp.server.fastmcp` n'existe plus en mcp 2.x ; l'erreur renvoie au guide de migration | import provoqué, message lu |
| `from mcp.server import MCPServer` est le chemin canonique de la v2 | `docs/whats-new.md` du SDK, et import vérifié |
| `mcp.types.LATEST_PROTOCOL_VERSION == "2026-07-28"` | lecture de la constante |
| `DEFAULT_NEGOTIATED_VERSION == "2025-03-26"` | lecture de la constante |
| Un outil MCP annoté `-> ModelePydantic` produit `structured_content` = le dict du modèle ; annoté `-> list[X]` ou `-> X \| None`, la sortie est **enveloppée dans `{"result": ...}`** | appels réels sur le serveur en mémoire |
| `list_tools()` expose `.input_schema` / `.output_schema` en snake_case | introspection des objets renvoyés |
| `langgraph.types` fournit `Overwrite`, `interrupt`, `Command`, `RetryPolicy` | `hasattr` sur le module installé |
| `StateGraph.add_node` accepte `retry_policy`, `error_handler`, `timeout`, `cache_policy`, `defer`, `trace_policy` | `inspect.signature` |
| **La limite de récursion par défaut vaut 10007, pas 1000** | `langgraph/_internal/_config.py:32` puis `GraphRecursionError` provoquée |
| `trim_messages` a bien 9 paramètres, dans l'ordre annoncé | `inspect.signature` |
| `langfuse` 4 expose `run_experiment`, `Evaluation`, `RegressionError`, `observe(as_type=...)` avec `guardrail` et `evaluator` | introspection du client |
| Sans clés, le client Langfuse se désactive et ne lève pas | exécution sans variables d'environnement |
| **Des variables `LANGFUSE_*` présentes mais vides ne désactivent pas le SDK** : il ouvre un tracer et tente d'exporter. D'où le garde `actif()` avant tout appel | exécution avec `LANGFUSE_PUBLIC_KEY=` puis lecture de `Langfuse.__init__` (test `is None`) |
| Une page donne une seule trace (`create_trace_id(seed=thread_id)`), avec un span par nœud, un span par essai de repli et une `generation` par appel fournisseur portant modèle, tokens et coût | `tests/test_observabilite_generations.py`, spans lus dans un `InMemorySpanExporter` |
| `PostgresSaver` a bien `.from_conn_string()` et `.setup()` | introspection |
| En openai 3.14, `chat.completions.parse` existe hors beta | `hasattr` sur le client |
| L'image se construit et le conteneur passe son healthcheck en tournant non-root | `docker build` puis `docker run`, healthcheck observe `healthy` |
| `PostgresSaver.setup()` cree bien `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` | `\dt` dans le conteneur Postgres du compose |
| **Une generation en attente de validation survit au redemarrage du conteneur api** et reste validable ensuite | thread cree, `docker compose restart api`, relecture puis validation reussie |
| Rejouer une validation deja consommee renvoie 409, un brief vide renvoie 422 | appels curl contre le conteneur |
| **Le serveur Temporal auto-heberge tourne dans le compose et le worker execute de vrais workflows** : workflow soumis depuis l'hote, execute par le worker du conteneur, page publiee | `docker compose up` puis `client.execute_workflow(GenerationPage.run, ...)` |
| Les quatre services (api, base, temporal, worker) tiennent ensemble dans ~460 Mo | `docker stats` sur la stack complete |
| `WorkflowEnvironment.start_time_skipping()` demarre **sans acces reseau externe** : le serveur de test est embarque dans le SDK, rien n'est telecharge | resolution DNS bloquee puis demarrage reussi |
| Le SDK Langfuse a **deux chemins d'export distincts** : les spans en OTLP protobuf vers `/api/public/otel/v1/traces`, les scores en REST JSON vers `/api/public/ingestion` avec `Authorization: Basic` | lecture de `langfuse/_client/span_processor.py` et `langfuse/_utils/request.py` |
| **La CI passe sur un runner GitHub reel** : lint, format, la suite de tests, puis la porte de non-regression sur le golden dataset | run public du depot (mesure anterieure a ce changement, 119 tests a l'epoque), `actions/checkout@v7` et `actions/setup-python@v7` |
| `.venv/bin/pytest -q` passe apres ce changement : 153 passed, 3 skipped, en 6,56 s | execution locale du 16/09/2026 |
| Les routes de l'API sont des fonctions `def` : `mcp.Client(construire())` et `asyncio.run()` s'executent donc dans le pool de threads de FastAPI, jamais sur la boucle asyncio de la requete, et la resolution de prix aboutit depuis une route synchrone | `tests/test_api.py`, requete HTTP de bout en bout jusqu'a `prix_affiche` |
| `mcp.Client` accepte une instance `Server` ou `MCPServer` pour une connexion en memoire, sans process ni socket ; la docstring la presente comme un usage de test, repris ici comme mecanisme de production | docstring de `mcp.client.client.Client` (mcp 2.2.0 installe) et `fabrique/mcp_catalogue/client.py`, exerce par `tests/test_mcp_catalogue.py` |
| Dans `Tool.run` (mcp 2.2.0), un `ToolError` leve deliberement par l'outil garde son propre texte dans le `CallToolResult(isError=True)` renvoye au client ; toute autre exception devient un `UnexpectedToolError` au message generique, sans le texte d'origine | lecture de `mcp/server/mcpserver/tools/base.py`, et `tests/test_mcp_catalogue.py::test_le_client_leve_runtimeerror_en_cas_de_crash_catalogue` qui verifie que le crash simule ne contient pas le texte "reference inconnue" |
| `SkipJsonSchema[str \| None]` retire entierement le champ `prix_affiche` de `BlocPage.model_json_schema()`, sans changer la validation du champ | `BlocPage.model_json_schema()["properties"]` execute en local : `prix_affiche` absent |
| **Une instance Langfuse auto-hebergee recoit et conserve la telemetrie de la fabrique** : 5 observations `GUARDRAIL` et 5 scores `LIEN_MORT` issus de vraies generations, lus via `/api/public/v3/scores` | stack Langfuse complete lancee en local (6 services, ~3 Go), projet provisionne par `LANGFUSE_INIT_*` |
| **L'API refuse un score sans point d'ancrage** (`traceId`, `observationId`, `sessionId` ou `datasetRunId`) en 400, alors que la signature de `create_score` presente tous ces champs comme optionnels | POST direct sur `/api/public/ingestion`, avec et sans `traceId` |
| **La telemetrie sort reellement du processus** : un recepteur HTTP local recoit un evenement `score-create` apres une vraie generation | `tests/test_observabilite_reseau.py` |
| Les reponses HTTP exposent le fournisseur qui a repondu et le cout de la page | test `test_la_reponse_expose_qui_a_repondu_et_le_cout` |
| Le noeud de controle appelle bien `tracer_violation` : l'instrumentation est cablee, pas decorative | test `test_le_noeud_de_controle_trace_les_violations` |
| **Une cle invalide est classee `Fatale`, pas `Surcharge`** : le repli ne boucle donc pas sur une erreur definitive | `tests/test_providers_reels.py`, appel reel avec une cle bidon |
| **L'adaptateur Anthropic fonctionne contre l'API reelle** sur `claude-sonnet-5` : appel abouti, reponse parsee, erreurs traduites vers la taxonomie | `scripts_valider_fournisseur.py anthropic`, qui instanciait alors l'adaptateur avec `claude-sonnet-5`, son defaut d'alors ; `FournisseurAnthropic` exige desormais `modele` en argument, sans defaut propre, et le script passe le modele des `Reglages` |
| **La boucle de reparation repare contre un vrai modele** : face a une `meta_description` hors bornes, l'erreur nommant le champ est renvoyee au modele et le second jet est conforme | execution avec `generer_valide(max_essais=3)` |
| **L'adaptateur OVHcloud fonctionne contre l'API reelle** : `Meta-Llama-3_3-70B-Instruct` a repondu, 65 tokens entree / 546 sortie, Page valide au premier essai grace a `response_format` | `scripts_valider_fournisseur.py ovhcloud` avec une vraie cle |
| **Le graphe complet tourne contre un vrai modele** : violation bloquante detectee, correction reinjectee, second jet conforme, interruption pour validation, publication unique apres approbation | execution du graphe avec `FournisseurAnthropic` |

## Faits établis par lecture de la documentation officielle

| Fait | Source |
|---|---|
| `interrupt()` + `Command(resume=...)` pour la validation humaine ; exige un checkpointer et un `thread_id` | [docs.langchain.com — interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) |
| Un nœud contenant un `interrupt()` est rejoué depuis le début ; les effets de bord vont dans un nœud séparé, et toute écriture antérieure doit être idempotente (upsert) | [docs.langchain.com — interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) |
| `PostgresSaver.from_conn_string(...)` puis `.setup()` en production ; `InMemorySaver` ne survit pas au redémarrage | [docs.langchain.com — persistence](https://docs.langchain.com/oss/python/langgraph/persistence) |
| AI Endpoints est compatible OpenAI ; `base_url='https://oai.endpoints.kepler.ai.cloud.ovh.net/v1'` ; `response_format` accepte un modèle Pydantic ; modèle documenté `Meta-Llama-3_3-70B-Instruct` | [docs.ovhcloud.com — structured output](https://docs.ovhcloud.com/en/guides/public-cloud/ai-machine-learning/ai-endpoints-structured-output) |
| « Structured output currently supports a subset of the JSON schema specification. Some features may not be compatible. » — c'est ce qui justifie la boucle de réparation | même page |
| Les six contraintes de déterminisme Temporal, mot pour mot | [docs.temporal.io — workflow basics](https://docs.temporal.io/develop/python/workflows/basics) |
| Le serveur Temporal est sous licence MIT : l'auto-hébergement est libre, c'est Temporal Cloud qui est payant | [github.com/temporalio/temporal](https://github.com/temporalio/temporal) |
| Langfuse est MIT (hors `ee/`) et auto-hébergeable, au prix de quatre services : Postgres, ClickHouse, Redis, S3 | [langfuse.com/self-hosting](https://langfuse.com/self-hosting), voir [`langfuse.md`](langfuse.md) |
| « When you declare a path operation function with normal `def` instead of `async def`, it is run in an external threadpool that is then awaited, instead of being called directly (as it would block the server). » | [fastapi.tiangolo.com/async](https://fastapi.tiangolo.com/async/) — « Very Technical Details » |
| « The `SkipJsonSchema` annotation can be used to skip an included field (or part of a field's specifications) from the generated JSON schema. » | [docs/concepts/json_schema.md#skipjsonschema-annotation](https://github.com/pydantic/pydantic/blob/main/docs/concepts/json_schema.md), pydantic 2.13.5 installe |

## Position d'auteur, à présenter comme telle

La grille règle / outil / dataset / juge, la taxonomie d'erreurs en quatre
catégories, l'ordre de priorité des quatre leviers de contexte, les six métriques
de tableau de bord, et les parades au trop grand nombre d'outils. Rien de tout
cela n'est tiré d'une spécification : ce sont des positions défendables, pas des
citations.

## Limites de couverture

La CI tourne sur le fournisseur factice. C'est délibéré : un test qui coûte de
l'argent ou dépend d'un service tiers finit désactivé. Les adaptateurs réels ont
leurs propres tests d'intégration dans `tests/test_providers_reels.py`, ignorés
par défaut et lancés à la demande avec `FABRIQUE_TESTS_REELS=1`.

La porte de non-régression rejoue le golden dataset sur ce même fournisseur
factice : elle protège la plomberie (graphe, garde-fous, boucle de réparation,
évaluateurs), pas la qualité d'un vrai modèle.

Haiku 4.5 (`claude-haiku-4-5-20251001`) est le modèle Anthropic par défaut de la
configuration et la cible de `tests/test_providers_reels.py`, mais aucune
exécution de ce test n'est consignée : Haiku 4.5 n'est pas vérifié ici, et son
coût par page reste une projection à partir du tarif publié.

Le chemin Temporal n'est pas branché sur l'API : aucune route ne démarre de
workflow. `tests/test_temporal.py` l'exécute dans le serveur de test du SDK, et le
worker du compose l'a exécuté sur soumission manuelle depuis l'hôte.

Le déploiement sur une infrastructure réelle reste à faire : tout ce qui précède
tourne en local ou sur un runner GitHub.
