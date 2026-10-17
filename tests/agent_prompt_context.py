"""The context a turn's request gave the model, whole, whatever the prompt layout (agent/prompts.py).

The cache-stable layout sends it in two messages - the conversation's setting (`context: {...}`) before the
conversation and this turn's part (`context (this turn; ...): {...}`) after it - and the legacy layout in one. Tests
read the context as one document either way.
"""

from __future__ import annotations

import json

from writing_coach.agent.prompts import TURN_CONTEXT_HEAD


def context_of(messages) -> dict:
    """The context of a request (its messages, or their contents), merged in the order sent."""

    merged: dict = {}
    for message in messages:
        content = getattr(message, "content", message)
        if content.startswith("context: "):
            merged.update(json.loads(content[len("context: "):]))
        elif content.startswith(TURN_CONTEXT_HEAD):
            merged.update(json.loads(content[len(TURN_CONTEXT_HEAD):]))
    if not merged:
        raise StopIteration("no context message")
    return merged
