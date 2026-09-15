from __future__ import annotations

import json
import subprocess
import sys
import types

import pytest
from pydantic import BaseModel

from fabrique.providers.base import Fatale, Reponse, SortieInvalide, Surcharge
from fabrique.providers.fake import FournisseurFake


class Schema(BaseModel):
    valeur: str


def test_fake_est_deterministe_sans_reponses_fournies() -> None:
    fournisseur = FournisseurFake()

    reponse_1 = fournisseur.generer(invite="a", schema=Schema)
    reponse_2 = fournisseur.generer(invite="a", schema=Schema)

    assert reponse_1 == reponse_2
    assert isinstance(reponse_1, Reponse)
    Schema.model_validate_json(reponse_1.texte)


def test_fake_sert_les_reponses_dans_l_ordre_puis_rejoue_la_derniere() -> None:
    fournisseur = FournisseurFake(reponses=['{"valeur": "un"}', '{"valeur": "deux"}'])

    r1 = fournisseur.generer(invite="a", schema=Schema)
    r2 = fournisseur.generer(invite="a", schema=Schema)
    r3 = fournisseur.generer(invite="a", schema=Schema)

    assert json.loads(r1.texte) == {"valeur": "un"}
    assert json.loads(r2.texte) == {"valeur": "deux"}
    assert json.loads(r3.texte) == {"valeur": "deux"}


def test_fake_rejoue_la_sequence_d_erreurs() -> None:
    fournisseur = FournisseurFake(erreurs=[Surcharge(), None])

    with pytest.raises(Surcharge):
        fournisseur.generer(invite="a", schema=Schema)

    reponse = fournisseur.generer(invite="a", schema=Schema)
    assert isinstance(reponse, Reponse)


def test_fake_transmet_le_retour_dans_les_appels_enregistres() -> None:
    fournisseur = FournisseurFake()

    fournisseur.generer(invite="a", schema=Schema, retour=None)
    fournisseur.generer(invite="a", schema=Schema, retour="erreur de validation")

    assert fournisseur.appels[0] == {"invite": "a", "retour": None}
    assert fournisseur.appels[1] == {"invite": "a", "retour": "erreur de validation"}


def _module_openai_factice() -> types.ModuleType:
    module = types.ModuleType("openai")

    class OpenAIError(Exception):
        pass

    class RateLimitError(OpenAIError):
        pass

    class APIConnectionError(OpenAIError):
        pass

    class APITimeoutError(OpenAIError):
        pass

    class AuthenticationError(OpenAIError):
        pass

    class PermissionDeniedError(OpenAIError):
        pass

    class NotFoundError(OpenAIError):
        pass

    class LengthFinishReasonError(OpenAIError):
        pass

    class ContentFilterFinishReasonError(OpenAIError):
        pass

    class OpenAI:
        def __init__(self, *args, **kwargs) -> None:
            pass

    module.OpenAIError = OpenAIError
    module.RateLimitError = RateLimitError
    module.APIConnectionError = APIConnectionError
    module.APITimeoutError = APITimeoutError
    module.AuthenticationError = AuthenticationError
    module.PermissionDeniedError = PermissionDeniedError
    module.NotFoundError = NotFoundError
    module.LengthFinishReasonError = LengthFinishReasonError
    module.ContentFilterFinishReasonError = ContentFilterFinishReasonError
    module.OpenAI = OpenAI
    return module


@pytest.fixture
def fournisseur_ovhcloud(monkeypatch: pytest.MonkeyPatch):
    faux_openai = _module_openai_factice()
    monkeypatch.setitem(sys.modules, "openai", faux_openai)
    sys.modules.pop("fabrique.providers.ovhcloud", None)

    from fabrique.providers.ovhcloud import FournisseurOVHcloud

    fournisseur = FournisseurOVHcloud(api_key="cle-de-test")
    yield fournisseur, faux_openai


def _patch_parse(fournisseur: object, effet) -> None:
    class Completions:
        def parse(self, **kwargs):
            return effet(**kwargs)

    class Chat:
        completions = Completions()

    fournisseur._client.chat = Chat()


def test_ovhcloud_traduit_rate_limit_en_surcharge(fournisseur_ovhcloud) -> None:
    fournisseur, faux_openai = fournisseur_ovhcloud

    def leve(**kwargs):
        raise faux_openai.RateLimitError("429")

    _patch_parse(fournisseur, leve)

    with pytest.raises(Surcharge):
        fournisseur.generer(invite="a", schema=Schema)


def test_ovhcloud_traduit_erreurs_connexion_en_surcharge(fournisseur_ovhcloud) -> None:
    fournisseur, faux_openai = fournisseur_ovhcloud

    def leve(**kwargs):
        raise faux_openai.APIConnectionError("connexion")

    _patch_parse(fournisseur, leve)

    with pytest.raises(Surcharge):
        fournisseur.generer(invite="a", schema=Schema)


@pytest.mark.parametrize(
    "nom_exception",
    ["AuthenticationError", "PermissionDeniedError", "NotFoundError"],
)
def test_ovhcloud_traduit_erreurs_credentials_en_fatale(
    fournisseur_ovhcloud, nom_exception: str
) -> None:
    fournisseur, faux_openai = fournisseur_ovhcloud
    classe_exception = getattr(faux_openai, nom_exception)

    def leve(**kwargs):
        raise classe_exception("acces refuse")

    _patch_parse(fournisseur, leve)

    with pytest.raises(Fatale):
        fournisseur.generer(invite="a", schema=Schema)


def test_ovhcloud_traduit_refus_en_sortie_invalide(fournisseur_ovhcloud) -> None:
    fournisseur, _ = fournisseur_ovhcloud

    class Message:
        refusal = "je ne peux pas repondre a cela"
        parsed = None

    class Choice:
        message = Message()

    class Completion:
        choices = [Choice()]
        model = "test"
        usage = None

    _patch_parse(fournisseur, lambda **kwargs: Completion())

    with pytest.raises(SortieInvalide):
        fournisseur.generer(invite="a", schema=Schema)


def test_ovhcloud_transmet_le_retour_dans_les_messages(fournisseur_ovhcloud) -> None:
    fournisseur, _ = fournisseur_ovhcloud
    messages_captures: dict = {}

    class Message:
        refusal = None
        parsed = Schema(valeur="ok")

    class Choice:
        message = Message()

    class Completion:
        choices = [Choice()]
        model = "test"
        usage = None

    def capture(**kwargs):
        messages_captures.update(kwargs)
        return Completion()

    _patch_parse(fournisseur, capture)

    fournisseur.generer(invite="question", schema=Schema, retour="erreur precedente")

    contenu_messages = [m["content"] for m in messages_captures["messages"]]
    assert any("erreur precedente" in c for c in contenu_messages)


def test_importer_le_module_ne_charge_pas_le_sdk() -> None:
    """L'import doit rester paresseux, que le paquet soit installe ou non."""
    code = "import sys; import fabrique.providers.anthropic; print('anthropic' in sys.modules)"
    sortie = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert sortie.stdout.strip() == "False"


def test_construire_sans_le_paquet_donne_une_erreur_claire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import fabrique.providers.anthropic as module_anthropic

    monkeypatch.setitem(sys.modules, "anthropic", None)
    with pytest.raises(ImportError):
        module_anthropic.FournisseurAnthropic(api_key="cle-de-test")


def _module_anthropic_factice() -> types.ModuleType:
    module = types.ModuleType("anthropic")

    class AnthropicError(Exception):
        pass

    class RateLimitError(AnthropicError):
        pass

    class OverloadedError(AnthropicError):
        pass

    class APIConnectionError(AnthropicError):
        pass

    class APITimeoutError(AnthropicError):
        pass

    class AuthenticationError(AnthropicError):
        pass

    class PermissionDeniedError(AnthropicError):
        pass

    class NotFoundError(AnthropicError):
        pass

    class Anthropic:
        def __init__(self, *args, **kwargs) -> None:
            pass

    module.AnthropicError = AnthropicError
    module.RateLimitError = RateLimitError
    module.OverloadedError = OverloadedError
    module.APIConnectionError = APIConnectionError
    module.APITimeoutError = APITimeoutError
    module.AuthenticationError = AuthenticationError
    module.PermissionDeniedError = PermissionDeniedError
    module.NotFoundError = NotFoundError
    module.Anthropic = Anthropic
    return module


@pytest.fixture
def fournisseur_anthropic(monkeypatch: pytest.MonkeyPatch):
    faux_anthropic = _module_anthropic_factice()
    monkeypatch.setitem(sys.modules, "anthropic", faux_anthropic)
    sys.modules.pop("fabrique.providers.anthropic", None)

    from fabrique.providers.anthropic import FournisseurAnthropic

    fournisseur = FournisseurAnthropic(api_key="cle-de-test")
    yield fournisseur, faux_anthropic


def _patch_create(fournisseur: object, effet) -> None:
    class Messages:
        def create(self, **kwargs):
            return effet(**kwargs)

    fournisseur._client.messages = Messages()


def test_anthropic_traduit_rate_limit_en_surcharge(fournisseur_anthropic) -> None:
    fournisseur, faux_anthropic = fournisseur_anthropic

    def leve(**kwargs):
        raise faux_anthropic.RateLimitError("429")

    _patch_create(fournisseur, leve)

    with pytest.raises(Surcharge):
        fournisseur.generer(invite="a", schema=Schema)


def test_anthropic_traduit_overloaded_en_surcharge(fournisseur_anthropic) -> None:
    fournisseur, faux_anthropic = fournisseur_anthropic

    def leve(**kwargs):
        raise faux_anthropic.OverloadedError("529")

    _patch_create(fournisseur, leve)

    with pytest.raises(Surcharge):
        fournisseur.generer(invite="a", schema=Schema)


@pytest.mark.parametrize(
    "nom_exception",
    ["AuthenticationError", "PermissionDeniedError", "NotFoundError"],
)
def test_anthropic_traduit_erreurs_credentials_en_fatale(
    fournisseur_anthropic, nom_exception: str
) -> None:
    fournisseur, faux_anthropic = fournisseur_anthropic
    classe_exception = getattr(faux_anthropic, nom_exception)

    def leve(**kwargs):
        raise classe_exception("acces refuse")

    _patch_create(fournisseur, leve)

    with pytest.raises(Fatale):
        fournisseur.generer(invite="a", schema=Schema)


def test_anthropic_sans_bloc_tool_use_leve_sortie_invalide(fournisseur_anthropic) -> None:
    fournisseur, _ = fournisseur_anthropic

    class Message:
        content = []
        model = "test"
        usage = None

    _patch_create(fournisseur, lambda **kwargs: Message())

    with pytest.raises(SortieInvalide):
        fournisseur.generer(invite="a", schema=Schema)


def test_anthropic_sortie_non_conforme_leve_sortie_invalide(fournisseur_anthropic) -> None:
    fournisseur, _ = fournisseur_anthropic

    class BlocOutil:
        type = "tool_use"
        input = {"champ_inconnu": 1}

    class Message:
        content = [BlocOutil()]
        model = "test"
        usage = None

    _patch_create(fournisseur, lambda **kwargs: Message())

    with pytest.raises(SortieInvalide):
        fournisseur.generer(invite="a", schema=Schema)


def test_anthropic_transmet_le_retour_dans_les_messages(fournisseur_anthropic) -> None:
    fournisseur, _ = fournisseur_anthropic
    arguments_captures: dict = {}

    class BlocOutil:
        type = "tool_use"
        input = {"valeur": "ok"}

    class Message:
        content = [BlocOutil()]
        model = "test"
        usage = None

    def capture(**kwargs):
        arguments_captures.update(kwargs)
        return Message()

    _patch_create(fournisseur, capture)

    fournisseur.generer(invite="question", schema=Schema, retour="erreur precedente")

    contenu_messages = [m["content"] for m in arguments_captures["messages"]]
    assert any("erreur precedente" in c for c in contenu_messages)
