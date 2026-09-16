"""Ce que Langfuse recoit d'une generation de page, lu dans les spans exportes
par la fixture `spans` (`tests/conftest.py`).
"""

from __future__ import annotations

import json

import pytest
from langfuse import Langfuse
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from pydantic import BaseModel

from fabrique import observabilite
from fabrique.config import reglages
from fabrique.generation.graphe import construire
from fabrique.providers.anthropic import FournisseurAnthropic
from fabrique.providers.base import SortieInvalide, Surcharge
from fabrique.providers.fake import FournisseurFake
from fabrique.providers.ovhcloud import FournisseurOVHcloud

TYPE = "langfuse.observation.type"
NIVEAU = "langfuse.observation.level"
MODELE = "langfuse.observation.model.name"
USAGE = "langfuse.observation.usage_details"
COUT = "langfuse.observation.cost_details"


class Schema(BaseModel):
    valeur: str


def _generations(spans) -> list:
    return [s for s in spans if s.attributes.get(TYPE) == "generation"]


def _page(titres: int) -> str:
    blocs = [{"type": "titre", "contenu": f"Titre {n}"} for n in range(titres)]
    blocs.append({"type": "paragraphe", "contenu": "Un paragraphe sans prix."})
    return json.dumps(
        {"titre_h1": "Titre", "meta_description": "A" * 130, "blocs": blocs, "liens": []}
    )


def test_une_page_donne_une_trace_de_la_redaction_a_la_publication(spans, monkeypatch) -> None:
    monkeypatch.setattr("fabrique.generation.graphe.tracer_violation", lambda v: None)
    fournisseur = FournisseurFake(reponses=[_page(titres=2), _page(titres=1)])
    graphe = construire([fournisseur], set(), checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "page-1"}}

    graphe.invoke({"brief": "page"}, config=config)
    graphe.invoke(Command(resume={"approuve": True, "commentaire": ""}), config=config)

    exportes = spans()
    assert {format(s.context.trace_id, "032x") for s in exportes} == {
        Langfuse.create_trace_id(seed="page-1")
    }, "la reprise apres validation doit rester dans la trace de la page"
    noeuds = [s.name for s in exportes if s.attributes.get("langfuse.internal.as_root")]
    assert noeuds == [
        "redaction",
        "controle",
        "correction",
        "redaction",
        "controle",
        "tarification",
        "publication",
    ]
    generations = _generations(exportes)
    assert len(generations) == 2
    assert all(g.attributes[MODELE] == "fake" for g in generations)
    assert json.loads(generations[0].attributes[USAGE]) == {"input": 0, "output": 0}
    essais = {s.context.span_id for s in exportes if s.name == "essai fake"}
    assert all(g.parent.span_id in essais for g in generations)


def test_le_repli_laisse_l_erreur_visible_dans_la_trace(spans, monkeypatch) -> None:
    monkeypatch.setattr("fabrique.generation.graphe.tracer_violation", lambda v: None)
    sature = FournisseurFake(erreurs=[Surcharge("429")])
    graphe = construire([sature, FournisseurFake()], set(), checkpointer=InMemorySaver())

    graphe.invoke({"brief": "page"}, config={"configurable": {"thread_id": "page-2"}})

    niveaux = [s.attributes.get(NIVEAU) for s in _generations(spans())]
    assert niveaux == ["ERROR", None]


def test_anthropic_enregistre_modele_usage_et_cout(spans) -> None:
    fournisseur = FournisseurAnthropic(api_key="cle-de-test", modele="claude-haiku-4-5-20251001")

    class BlocOutil:
        type = "tool_use"
        input = {"valeur": "ok"}

    class Usage:
        input_tokens = 1_000
        output_tokens = 200

    class Message:
        content = [BlocOutil()]
        model = "claude-haiku-4-5-20251001"
        usage = Usage()

    class Messages:
        def create(self, **kwargs):
            return Message()

    fournisseur._client.messages = Messages()

    fournisseur.generer(invite="a", schema=Schema)

    (generation,) = _generations(spans())
    assert generation.attributes[MODELE] == "claude-haiku-4-5-20251001"
    assert json.loads(generation.attributes[USAGE]) == {"input": 1_000, "output": 200}
    assert json.loads(generation.attributes[COUT]) == pytest.approx(
        {"input": 0.001, "output": 0.001}
    )


def test_anthropic_sans_tarif_connu_ne_declare_pas_de_cout(spans) -> None:
    fournisseur = FournisseurAnthropic(api_key="cle-de-test", modele="claude-sonnet-5")

    class Message:
        content = []
        model = "claude-sonnet-5"
        usage = None

    class Messages:
        def create(self, **kwargs):
            return Message()

    fournisseur._client.messages = Messages()

    with pytest.raises(SortieInvalide):
        fournisseur.generer(invite="a", schema=Schema)

    (generation,) = _generations(spans())
    assert COUT not in generation.attributes
    assert generation.attributes[NIVEAU] == "ERROR"


def test_ovhcloud_enregistre_l_usage_et_le_cout_en_euros(spans) -> None:
    fournisseur = FournisseurOVHcloud(api_key="cle-de-test")

    class Message:
        refusal = None
        parsed = Schema(valeur="ok")

    class Choice:
        message = Message()

    class Usage:
        prompt_tokens = 65
        completion_tokens = 546

    class Completion:
        choices = [Choice()]
        model = "Meta-Llama-3_3-70B-Instruct"
        usage = Usage()

    class Completions:
        def parse(self, **kwargs):
            return Completion()

    class Chat:
        completions = Completions()

    fournisseur._client.chat = Chat()

    fournisseur.generer(invite="a", schema=Schema)

    (generation,) = _generations(spans())
    assert json.loads(generation.attributes[USAGE]) == {"input": 65, "output": 546}
    assert COUT not in generation.attributes, "cost_details est en USD, le tarif en EUR"
    cout_eur = float(generation.attributes["langfuse.observation.metadata.cout_eur"])
    assert cout_eur == pytest.approx(611 * 0.67 / 1_000_000)


def test_des_cles_vides_n_exportent_rien(spans, monkeypatch) -> None:
    """Le cas de `.env.exemple` : variables presentes mais vides."""
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "")
    reglages.cache_clear()
    assert observabilite.actif() is False

    graphe = construire([FournisseurFake()], set(), checkpointer=InMemorySaver())
    graphe.invoke({"brief": "page"}, config={"configurable": {"thread_id": "page-3"}})

    assert spans() == ()
