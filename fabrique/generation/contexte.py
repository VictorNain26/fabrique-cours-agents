"""Compaction du contexte sous un budget de tokens.

langchain-core fournit `trim_messages(messages, *, max_tokens, token_counter,
strategy, allow_partial, end_on, start_on, include_system, text_splitter)`
pour le cas standard des messages de chat. Cette implementation existe parce
que les unites manipulees par la fabrique ne sont pas des messages de chat
mais des briefs, des sections generees et des resultats d'appels d'outils,
que `trim_messages` ne modelise pas.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypedDict


class Message(TypedDict):
    role: str
    contenu: str
    tokens: int


def estimer(texte: str) -> int:
    return max(1, len(texte) // 4)


def compacter(
    messages: list[dict],
    budget: int,
    resumer: Callable[[list[dict]], str],
) -> list[dict]:
    systemes = [m for m in messages if m["role"] == "system"]
    autres = [m for m in messages if m["role"] != "system"]

    cout_systemes = sum(m["tokens"] for m in systemes)

    gardes: list[dict] = []
    ecartes: list[dict] = []
    cout_gardes = 0
    for message in reversed(autres):
        if cout_systemes + cout_gardes + message["tokens"] <= budget:
            gardes.append(message)
            cout_gardes += message["tokens"]
        else:
            ecartes.append(message)
    gardes.reverse()
    ecartes.reverse()

    if not ecartes:
        return systemes + gardes

    resume = resumer(ecartes)
    message_resume: dict = {"role": "system", "contenu": resume, "tokens": estimer(resume)}

    while gardes and cout_systemes + message_resume["tokens"] + cout_gardes > budget:
        retire = gardes.pop(0)
        cout_gardes -= retire["tokens"]

    return systemes + [message_resume] + gardes
