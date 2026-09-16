# Langfuse — auto-hebergement

## Licence

Le depot [`langfuse/langfuse`](https://github.com/langfuse/langfuse) est MIT
Expat en dehors des repertoires `ee/`, `web/src/ee/` et `worker/src/ee/`
(licence propriétaire pour ces trois-la). Verifie sur
`https://github.com/langfuse/langfuse/blob/main/LICENSE` le 16/09/2026. C'est
un argument reel chez un hebergeur : le coeur du produit peut tourner sans
compte cloud Langfuse.

## Ce que la v3/v4 exige comme services

Source : `https://langfuse.com/self-hosting` (consultee le 16/09/2026, page
titree "Version: v4" — les briques n'ont pas change depuis la v3 evoquee dans
ce depot). Quatre dependances d'infrastructure :

- **Postgres** — base transactionnelle principale.
- **ClickHouse** — base OLAP qui stocke traces, observations et scores.
- **Redis/Valkey** — file d'attente et cache en memoire.
- **S3 / stockage objet** — persistance des evenements entrants, des entrees
  multimodales et des exports volumineux.

Plus deux conteneurs applicatifs : Langfuse Web (interface + API) et Langfuse
Worker (traitement asynchrone). C'est exactement pourquoi ce projet ne lance
pas Langfuse en local : quatre services d'etat en plus de deux conteneurs
applicatifs ne tiennent pas dans ~4 Go de RAM libre.

## Brancher ce projet sur une instance Langfuse

Trois variables, deja declarees dans `fabrique/config.py` (`Reglages`) et
documentees dans `.env.exemple` :

```
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

`LANGFUSE_HOST` pointe vers `https://cloud.langfuse.com` par defaut ; pour une
instance auto-hebergee, remplacer par son URL (ex. `https://langfuse.interne`).
Le SDK Python 4.15.3 installe ici lit en priorite `LANGFUSE_BASE_URL`, sinon
`LANGFUSE_HOST` (verifie par lecture directe de
`.venv/lib/python3.12/site-packages/langfuse/_client/client.py`, ~ligne 341) ;
ce depot n'utilise que `LANGFUSE_HOST`, ce qui reste un chemin supporte. Sans
ces cles, `fabrique.observabilite.actif()` renvoie `False` et toute
l'instrumentation devient un no-op — voir `tests/test_observabilite.py`.

Le garde `actif()` passe avant le SDK pour une raison precise : le SDK ne se
desactive que si `LANGFUSE_PUBLIC_KEY` est **absente**. Presente mais vide, ce
que donne `.env.exemple` repris par docker compose, elle suffit a ouvrir un
tracer et un exporteur (verifie par execution sur 4.15.3, voir
`Langfuse.__init__` dans `langfuse/_client/client.py`, test `is None`).

## Ce que la fabrique envoie

- une trace par page, `trace_id = create_trace_id(seed=thread_id)`, nommee
  `page`, `session_id` egal au `thread_id` ;
- un span par noeud `redaction`, `controle`, `correction`, `publication` ;
- un span par essai de la chaine de repli (`essai <fournisseur>`), en `ERROR`
  quand le fournisseur leve ;
- une observation `generation` par appel fournisseur : `model`,
  `usage_details` (`input`, `output`), `cost_details` en USD quand le tarif est
  connu (Haiku 4.5), `cout_eur` en metadonnee pour OVHcloud ;
- une observation `guardrail` et un score booleen par violation.

Sources : `usage_details` et `cost_details` (cout en USD) —
https://github.com/langfuse/langfuse-docs/blob/main/content/docs/observability/features/token-and-cost-tracking.mdx ;
`trace_context` et `create_trace_id(seed=...)` —
https://github.com/langfuse/langfuse-docs/blob/main/content/docs/observability/features/trace-ids-and-distributed-tracing.mdx ;
signatures relues dans `langfuse/_client/client.py` (4.15.3).

## Ce qui n'a pas ete verifie ici, et pourquoi

L'auto-hebergement (docker compose Postgres + ClickHouse + Redis + Minio +
Langfuse Web/Worker) n'a **pas** ete lance dans cet environnement : la machine
ne dispose que d'environ 4 Go de RAM libre, insuffisant pour ces six services.
La preuve que l'instrumentation emet reellement de la telemetrie est apportee
autrement, par `tests/test_observabilite_reseau.py` : un recepteur HTTP local
(pas un serveur Langfuse) encaisse la requete que le SDK envoie et son corps
est verifie. Cela prouve que le SDK emet une requete avec le bon contenu, pas
qu'une instance Langfuse reelle l'accepterait.

Les observations `generation`, leurs tokens et leurs couts n'ont pas ete
renvoyes a l'instance auto-hebergee evoquee dans `docs/verification.md` :
`tests/test_observabilite_generations.py` verifie les attributs
`langfuse.observation.*` poses sur les spans, dans un exporteur en memoire,
pas leur affichage dans l'interface.
