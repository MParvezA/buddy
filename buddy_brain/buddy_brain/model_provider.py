# Copyright 2026 SyncRobot

"""Narrow, local-model-only protocol used by the dialogue core."""

from collections.abc import Callable
from typing import Protocol


class LocalModelProvider(Protocol):
    """Produces one JSON response from a pre-summarized dialogue context."""

    def complete(self, context_json: str) -> str:
        """Return one model response; the caller validates it before use."""


class LocalModelAdapter:
    """Adapts an explicitly injected local completion function to the protocol."""

    def __init__(self, complete_fn: Callable[[str], str]) -> None:
        self._complete_fn = complete_fn

    def complete(self, context_json: str) -> str:
        return self._complete_fn(context_json)


class DeterministicFakeProvider:
    """Test-only provider returning queued responses in a deterministic order."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self._responses = list(responses or [])
        self.contexts: list[str] = []

    def complete(self, context_json: str) -> str:
        self.contexts.append(context_json)
        if not self._responses:
            return '{"kind":"clarification","question":"What would you like Buddy to do?"}'
        return self._responses.pop(0)
