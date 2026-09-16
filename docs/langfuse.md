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

## Ce qui n'a pas ete verifie ici, et pourquoi

L'auto-hebergement (docker compose Postgres + ClickHouse + Redis + Minio +
Langfuse Web/Worker) n'a **pas** ete lance dans cet environnement : la machine
ne dispose que d'environ 4 Go de RAM libre, insuffisant pour ces six services.
La preuve que l'instrumentation emet reellement de la telemetrie est apportee
autrement, par `tests/test_observabilite_reseau.py` : un recepteur HTTP local
(pas un serveur Langfuse) encaisse la requete que le SDK envoie et son corps
est verifie. Cela prouve que le SDK emet une requete avec le bon contenu, pas
qu'une instance Langfuse reelle l'accepterait.
