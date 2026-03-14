from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ArchitectureRequest:
    github_url: str
    branch: str = "main"
    output_dir: str = "result"
    llm_provider: str = "openai"
    debug: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LLMConfig:
    provider: str
    model: str
    api_key: str | None = field(default=None, repr=False)
    api_key_source: str = "prompt"
    debug: bool = False

    def safe_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "api_key_source": self.api_key_source,
            "debug": self.debug,
        }


@dataclass(slots=True)
class RepositorySnapshot:
    github_url: str
    branch: str
    commit_sha: str
    fetched_at: str
    root_path: str
    language_hints: list[str]
    manifests: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GraphNode:
    id: str
    type: str
    label: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class GraphEdge:
    source: str
    target: str
    type: str
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ArchitectureGraph:
    repository: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "metadata": self.metadata,
            "nodes": [node.to_dict() for node in self.nodes],
            "edges": [edge.to_dict() for edge in self.edges],
        }


@dataclass(slots=True)
class AnalysisResult:
    metrics: dict[str, Any]
    findings: list[dict[str, Any]]
    explanations_markdown: str
    recommendations: list[dict[str, Any]]
