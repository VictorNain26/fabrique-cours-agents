"""Preuve par le reseau : le SDK Langfuse emet reellement une requete HTTP.

Aucun serveur Langfuse ne tourne ici (contrainte memoire, voir docs/langfuse.md).
Le recepteur ci-dessous n'est pas Langfuse : c'est un serveur HTTP minimal qui
encaisse ce que le SDK envoie, pour prouver que `tracer_violation` fait
vraiment sortir de la telemetrie du processus, pas seulement qu'il appelle les
bonnes fonctions Python.

`create_score` (utilise par `tracer_violation`) part par le client d'ingestion
REST du SDK (`langfuse/_utils/request.py::LangfuseClient.post`), pas par
l'exporteur OTLP des spans : la requete observee ici est un POST JSON vers
`/api/public/ingestion`, corps `{"batch": [...]}` contenant un evenement
`score-create`.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from langgraph.checkpoint.memory import InMemorySaver

from fabrique import observabilite
from fabrique.config import reglages
from fabrique.generation.graphe import construire
from fabrique.providers.fake import FournisseurFake

TIMEOUT_ATTENTE_SECONDES = 5.0


class _RecepteurIngestion(BaseHTTPRequestHandler):
    requetes: list[tuple[str, dict, bytes]] = []
    verrou = threading.Lock()

    def do_POST(self) -> None:  # noqa: N802 -- impose par BaseHTTPRequestHandler
        corps = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        with self.verrou:
            self.requetes.append((self.path, dict(self.headers), corps))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, format: str, *args: object) -> None:
        return


def _attendre_les_deux_chemins(timeout: float = TIMEOUT_ATTENTE_SECONDES) -> bool:
    """Les spans et les scores partent par deux chemins et deux files distinctes."""
    attendus = {"/api/public/otel/v1/traces", "/api/public/ingestion"}
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        if attendus <= {chemin for chemin, _, _ in _RecepteurIngestion.requetes}:
            return True
        time.sleep(0.02)
    return False


def test_tracer_violation_envoie_reellement_une_requete_http(monkeypatch) -> None:
    """Sans ceci, rien ne prouve qu'un octet quitte le processus vers Langfuse."""
    _RecepteurIngestion.requetes = []
    serveur = ThreadingHTTPServer(("127.0.0.1", 0), _RecepteurIngestion)
    thread_serveur = threading.Thread(target=serveur.serve_forever, daemon=True)
    thread_serveur.start()

    port = serveur.server_address[1]
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-reseau")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-reseau")
    monkeypatch.setenv("LANGFUSE_HOST", f"http://127.0.0.1:{port}")
    reglages.cache_clear()

    try:
        assert observabilite.actif() is True

        graphe = construire([FournisseurFake()], set(), checkpointer=InMemorySaver())
        graphe.invoke({"brief": "page"}, config={"configurable": {"thread_id": "reseau-1"}})

        observabilite.vider()

        assert _attendre_les_deux_chemins(), (
            "les deux chemins d export n ont pas ete empruntes : "
            f"{[c for c, _, _ in _RecepteurIngestion.requetes]}"
        )
    finally:
        serveur.shutdown()
        serveur.server_close()
        thread_serveur.join(timeout=2)
        reglages.cache_clear()

    chemins = [chemin for chemin, _, _ in _RecepteurIngestion.requetes]

    # Les deux chemins d'export du SDK : les spans en OTLP, les scores en REST.
    # L'ordre entre les deux n'est pas garanti, on n'assert donc que leur presence.
    assert "/api/public/otel/v1/traces" in chemins, chemins
    assert "/api/public/ingestion" in chemins, chemins

    ingestions = [
        (en_tetes, corps)
        for chemin, en_tetes, corps in _RecepteurIngestion.requetes
        if chemin == "/api/public/ingestion"
    ]
    en_tetes, corps = ingestions[0]
    assert en_tetes["Authorization"].startswith("Basic ")

    evenements = json.loads(corps)["batch"]
    assert any(e["type"] == "score-create" for e in evenements)
    ancres = [e["body"].get("traceId") for e in evenements if e["type"] == "score-create"]
    assert all(ancres), "un score sans traceId est refuse en 400 par l'API"
