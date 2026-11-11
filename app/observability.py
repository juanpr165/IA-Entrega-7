"""LangSmith instrumentation for the graph's LLM and node work."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

try:
    from langsmith import traceable
except ImportError:  # Allows importing unit-tested pure helpers without LangSmith installed.
    def traceable(*_args: Any, **_kwargs: Any) -> Callable[[Any], Any]:
        return lambda function: function


F = TypeVar("F", bound=Callable[..., Any])


def traced_node(name: str) -> Callable[[F], F]:
    """Decorate a node so LangSmith shows it as an individual trace span."""
    return traceable(name=name, run_type="chain")
