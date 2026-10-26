"""Tool capability manifest (design pattern P0: declared capabilities)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from clear.config import DEFAULT_MANIFEST, load_yaml

READ = "read"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    capability: str = READ
    sensitivity: float = 0.0
    reversible: bool = True
    target_args: tuple[str, ...] = ()
    content_args: tuple[str, ...] = ()
    value_args: tuple[str, ...] = ()
    output_trust: str = "untrusted"
    private_output: bool = False

    @property
    def is_side_effecting(self) -> bool:
        return self.capability != READ


@dataclass
class ToolManifest:
    tools: dict[str, ToolSpec] = field(default_factory=dict)
    defaults: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: str | Path | None = None) -> "ToolManifest":
        raw = load_yaml(path or DEFAULT_MANIFEST)
        defaults = raw.get("defaults", {})
        tools = {}
        for name, spec in (raw.get("tools") or {}).items():
            merged = dict(defaults, **(spec or {}))
            tools[name] = ToolSpec(
                name=name,
                capability=merged["capability"],
                sensitivity=float(merged["sensitivity"]),
                reversible=bool(merged["reversible"]),
                target_args=tuple(merged.get("target_args") or ()),
                content_args=tuple(merged.get("content_args") or ()),
                value_args=tuple(merged.get("value_args") or ()),
                output_trust=merged["output_trust"],
                private_output=bool(merged["private_output"]),
            )
        return cls(tools=tools, defaults=defaults)

    def get(self, name: str) -> ToolSpec:
        """Unknown tools fail closed: treated as side-effecting and sensitive."""
        if name in self.tools:
            return self.tools[name]
        return ToolSpec(name=name, capability="unknown", sensitivity=0.8, reversible=False,
                        output_trust="untrusted")
