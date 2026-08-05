from __future__ import annotations

from dataclasses import dataclass, field

from arklight.ir.schema import SCHEMA
from arklight.search._tokenize import tokenize


@dataclass(frozen=True)
class SymbolFact:
    name: str
    required_props: tuple[str, ...] = field(default_factory=tuple)
    allow_children: bool = True
    text_only_children: bool = False
    tokens: tuple[str, ...] = field(default_factory=tuple)


def build_knowledge_base() -> dict[str, SymbolFact]:
    facts: dict[str, SymbolFact] = {}
    for name, spec in SCHEMA.items():
        facts[name] = SymbolFact(
            name=name,
            required_props=spec.required_props,
            allow_children=spec.allow_children,
            text_only_children=spec.text_only_children,
            tokens=tuple(tokenize(name)),
        )
    return facts
