"""Fixtures partagees entre modules de test.

`spans` fait sortir les traces Langfuse vers un exporteur OpenTelemetry en
memoire (parametre `span_exporter` du constructeur `Langfuse`, langfuse
4.15.3) : on lit les attributs `langfuse.observation.*`/`langfuse.trace.*`
que le SDK aurait envoyes, sans reseau. Un `TracerProvider` propre au test
evite de partager celui, global, que le SDK enregistre au premier client.
`LangfuseResourceManager.reset()` vide le registre des clients : `get_client()`
desactive le tracage des qu'il en trouve deux, et le test suivant laisse le
sien derriere lui.
"""

from __future__ import annotations

import pytest
from langfuse import Langfuse
from langfuse._client.resource_manager import LangfuseResourceManager
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from fabrique.config import reglages


@pytest.fixture
def spans(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test-memoire")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-test-memoire")
    reglages.cache_clear()
    LangfuseResourceManager.reset()
    exporteur = InMemorySpanExporter()
    client = Langfuse(
        public_key="pk-test-memoire",
        secret_key="sk-test-memoire",
        base_url="http://127.0.0.1:9",
        tracer_provider=TracerProvider(),
        span_exporter=exporteur,
    )

    def lire():
        client.flush()
        return exporteur.get_finished_spans()

    yield lire
    LangfuseResourceManager.reset()
    reglages.cache_clear()
