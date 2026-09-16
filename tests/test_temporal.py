from __future__ import annotations

import ast
import inspect
import json
import uuid

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from fabrique.generation.reparation import generer_valide
from fabrique.modeles import Page
from fabrique.providers.fake import FournisseurFake
from fabrique.temporal.activites import controler_page, publier_page
from fabrique.temporal.workflows import GenerationPage

TASK_QUEUE = "fabrique-test"
META = "A" * 130


def _page_json(titre_unique: bool) -> str:
    blocs = [{"type": "titre", "contenu": "Titre unique"}]
    if not titre_unique:
        blocs.append({"type": "titre", "contenu": "Second titre"})
    else:
        blocs.append({"type": "paragraphe", "contenu": "Un paragraphe sans prix."})
    return json.dumps(
        {
            "titre_h1": "Titre",
            "meta_description": META,
            "blocs": blocs,
            "liens": [],
        }
    )


PAGE_INVALIDE = _page_json(titre_unique=False)
PAGE_VALIDE = _page_json(titre_unique=True)


def _mock_generer_page(fake: FournisseurFake):
    @activity.defn(name="generer_page")
    async def generer_page(brief: str, retour: str | None) -> str:
        invite = brief if retour is None else f"{brief}\n\n{retour}"
        page = generer_valide(fake, invite=invite, schema=Page, systeme="test")
        return page.model_dump_json()

    return generer_page


@pytest.fixture
async def env():
    environment = await WorkflowEnvironment.start_time_skipping()
    yield environment
    await environment.shutdown()


async def _executer(env: WorkflowEnvironment, fake: FournisseurFake, brief: str) -> dict:
    async with Worker(
        env.client,
        task_queue=TASK_QUEUE,
        workflows=[GenerationPage],
        activities=[_mock_generer_page(fake), controler_page, publier_page],
    ):
        return await env.client.execute_workflow(
            GenerationPage.run,
            args=[brief, []],
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )


async def test_workflow_complet_publie_une_page(env: WorkflowEnvironment):
    fake = FournisseurFake(reponses=[PAGE_VALIDE])

    resultat = await _executer(env, fake, "brief")

    assert resultat["publiee"] is True
    assert resultat["identifiant_publication"]
    assert len(fake.appels) == 1


async def test_boucle_de_correction_fait_deux_tours(env: WorkflowEnvironment):
    fake = FournisseurFake(reponses=[PAGE_INVALIDE, PAGE_VALIDE])

    resultat = await _executer(env, fake, "brief")

    assert resultat["publiee"] is True
    assert len(fake.appels) == 2
    assert fake.appels[0]["invite"] == "brief"
    assert "H1_MULTIPLE" in fake.appels[1]["invite"]


async def test_borne_max_tours_sans_boucle_infinie(env: WorkflowEnvironment):
    fake = FournisseurFake(reponses=[PAGE_INVALIDE])

    resultat = await _executer(env, fake, "brief")

    assert resultat["publiee"] is False
    assert len(fake.appels) == 3


async def test_publication_idempotente():
    cle = f"idem-{uuid.uuid4()}"

    premier = await publier_page(PAGE_VALIDE, cle)
    second = await publier_page(PAGE_VALIDE, cle)

    assert premier == second


INTERDITS = {
    "datetime.now",
    "datetime.utcnow",
    "time.time",
    "random.random",
    "random.randint",
    "random.choice",
    "uuid.uuid4",
    "requests.get",
    "requests.post",
    "os.urandom",
}


def _appels(noeud: ast.AST) -> list[str]:
    out = []
    for n in ast.walk(noeud):
        if isinstance(n, ast.Call):
            f = n.func
            morceaux = []
            while isinstance(f, ast.Attribute):
                morceaux.append(f.attr)
                f = f.value
            if isinstance(f, ast.Name):
                morceaux.append(f.id)
            if morceaux:
                out.append(".".join(reversed(morceaux)))
    return out


def test_workflow_ne_contient_aucun_appel_non_deterministe():
    import fabrique.temporal.workflows as module

    source = inspect.getsource(module)
    corps = next(
        n
        for n in ast.walk(ast.parse(source))
        if isinstance(n, ast.ClassDef) and n.name == "GenerationPage"
    )

    fautifs = [a for a in _appels(corps) if a in INTERDITS]
    assert fautifs == []
