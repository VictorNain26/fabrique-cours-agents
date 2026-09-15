"""Tests de la compaction de contexte sous budget."""

from __future__ import annotations

from fabrique.generation.contexte import compacter, estimer


def message(role: str, contenu: str, tokens: int) -> dict:
    return {"role": role, "contenu": contenu, "tokens": tokens}


def echoue_si_appele(_messages: list[dict]) -> str:
    raise AssertionError("resumer ne doit pas etre appele quand tout tient dans le budget")


def test_rien_de_retire_si_tout_rentre():
    messages = [
        message("system", "regles", 5),
        message("user", "bonjour", 5),
        message("assistant", "salut", 5),
    ]

    resultat = compacter(messages, budget=100, resumer=echoue_si_appele)

    assert resultat == messages


def test_resumer_non_appele_pour_rien():
    messages = [
        message("system", "regles", 5),
        message("user", "question", 5),
    ]

    compacter(messages, budget=50, resumer=echoue_si_appele)


def test_budget_est_respecte():
    messages = [message("system", "regles", 10)] + [
        message("user" if i % 2 == 0 else "assistant", f"message {i}", 20) for i in range(10)
    ]

    def resumer(ecartes: list[dict]) -> str:
        return "resume court"

    resultat = compacter(messages, budget=60, resumer=resumer)

    assert sum(m["tokens"] for m in resultat) <= 60


def test_resumer_appele_une_seule_fois():
    compteur = {"appels": 0}

    def resumer(ecartes: list[dict]) -> str:
        compteur["appels"] += 1
        return "resume"

    messages = [message("system", "regles", 10)] + [
        message("user", f"message {i}", 30) for i in range(5)
    ]

    compacter(messages, budget=50, resumer=resumer)

    assert compteur["appels"] == 1


def test_messages_system_conserves():
    messages = [
        message("system", "regle 1", 5),
        message("system", "regle 2", 5),
    ] + [message("user", f"message {i}", 30) for i in range(5)]

    def resumer(ecartes: list[dict]) -> str:
        return "resume"

    resultat = compacter(messages, budget=50, resumer=resumer)

    systemes_resultat = [
        m for m in resultat if m["role"] == "system" and m["contenu"] in ("regle 1", "regle 2")
    ]
    assert [m["contenu"] for m in systemes_resultat] == ["regle 1", "regle 2"]
    assert resultat[0]["contenu"] == "regle 1"
    assert resultat[1]["contenu"] == "regle 2"


def test_message_le_plus_recent_present():
    messages = [message("system", "regles", 5)] + [
        message("user" if i % 2 == 0 else "assistant", f"message {i}", 20) for i in range(10)
    ]

    def resumer(ecartes: list[dict]) -> str:
        return "resume"

    resultat = compacter(messages, budget=60, resumer=resumer)

    assert resultat[-1]["contenu"] == "message 9"


def test_ordre_chronologique_preserve():
    messages = [message("system", "regles", 5)] + [
        message("user" if i % 2 == 0 else "assistant", f"message {i}", 15) for i in range(8)
    ]

    def resumer(ecartes: list[dict]) -> str:
        return "resume"

    resultat = compacter(messages, budget=70, resumer=resumer)

    contenus_non_system = [m["contenu"] for m in resultat if m["role"] != "system"]
    indices = [int(c.split()[-1]) for c in contenus_non_system]
    assert indices == sorted(indices)


def test_resume_insere_juste_apres_les_system_et_tient_dans_le_budget():
    messages = [message("system", "regles", 5)] + [
        message("user" if i % 2 == 0 else "assistant", f"message {i}", 25) for i in range(6)
    ]

    def resumer(ecartes: list[dict]) -> str:
        return "resume des messages ecartes"

    resultat = compacter(messages, budget=40, resumer=resumer)

    assert resultat[1]["role"] == "system"
    assert resultat[1]["contenu"] == "resume des messages ecartes"
    assert sum(m["tokens"] for m in resultat) <= 40


def test_estimer():
    assert estimer("") == 1
    assert estimer("abcd") == 1
    assert estimer("a" * 40) == 10
