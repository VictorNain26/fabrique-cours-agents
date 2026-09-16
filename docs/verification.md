# Registre de vérification — 15/09/2026

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
| `PostgresSaver` a bien `.from_conn_string()` et `.setup()` | introspection |
| En openai 3.14, `chat.completions.parse` existe hors beta | `hasattr` sur le client |
| L'image se construit et le conteneur passe son healthcheck en tournant non-root | `docker build` puis `docker run`, healthcheck observe `healthy` |
| `PostgresSaver.setup()` cree bien `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` | `\dt` dans le conteneur Postgres du compose |
| **Une generation en attente de validation survit au redemarrage du conteneur api** et reste validable ensuite | thread cree, `docker compose restart api`, relecture puis validation reussie |
| Rejouer une validation deja consommee renvoie 409, un brief vide renvoie 422 | appels curl contre le conteneur |
| Les reponses HTTP exposent le fournisseur qui a repondu et le cout de la page | test `test_la_reponse_expose_qui_a_repondu_et_le_cout` |
| Le noeud de controle appelle bien `tracer_violation` : l'instrumentation est cablee, pas decorative | test `test_le_noeud_de_controle_trace_les_violations` |
| **L'adaptateur Anthropic fonctionne contre l'API reelle** : appel abouti, reponse parsee, erreurs traduites vers la taxonomie. Couverture : `claude-sonnet-5`. Haiku 4.5, qui est le defaut, n'a pas ete appele | `scripts_valider_fournisseur.py anthropic` |
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

## Position d'auteur, à présenter comme telle

La grille règle / outil / dataset / juge, la taxonomie d'erreurs en quatre
catégories, l'ordre de priorité des quatre leviers de contexte, les six métriques
de tableau de bord, et les parades au trop grand nombre d'outils. Rien de tout
cela n'est tiré d'une spécification : ce sont des positions défendables, pas des
citations.

## Limites de couverture

Les tests automatisés et la CI tournent sur le fournisseur factice. C'est
délibéré : un test ne doit ni coûter d'argent ni dépendre d'un service tiers. Les
adaptateurs réels sont couverts par des tests sur la traduction de leurs erreurs,
et vérifiés à la main contre leur API.

Côté Anthropic, seul `claude-sonnet-5` a été appelé. Haiku 4.5 est le modèle par
défaut — le moins cher, cohérent avec un projet dont le coût par page est une
métrique — mais il n'a pas été exercé.

Le workflow GitHub Actions n'a jamais tourné sur un runner. `actions/checkout@v7`
et `actions/setup-python@v7` ont été relevées sur leurs pages de releases, pas
éprouvées.

Temporal n'est pas dans l'application : le chapitre 4 reste théorique. Langfuse
est instrumenté et le câblage est testé, mais aucun serveur Langfuse n'a jamais
reçu de trace.
