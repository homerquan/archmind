from __future__ import annotations

import ast
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from archmind.models import ArchitectureGraph, GraphEdge, GraphNode, RepositorySnapshot
from archmind.utils import compact_path, write_text


DATA_STORE_IMPORTS = {
    "sqlite3": "database",
    "sqlalchemy": "database",
    "psycopg": "database",
    "psycopg2": "database",
    "pymongo": "database",
    "redis": "cache",
    "shelve": "database",
}

EXTERNAL_SERVICE_IMPORTS = {
    "requests": "external_service",
    "httpx": "external_service",
    "aiohttp": "external_service",
    "grpc": "external_service",
    "boto3": "external_service",
}

QUEUE_IMPORTS = {
    "kafka": "queue",
    "pika": "queue",
    "celery": "queue",
}

OBSERVABILITY_IMPORTS = {"logging", "loguru", "structlog", "prometheus_client", "opentelemetry", "sentry_sdk"}
SECURITY_IMPORTS = {"jwt", "authlib", "bcrypt", "cryptography", "secrets", "ssl", "hashlib"}

READ_HINTS = {"get", "load", "read", "fetch", "query", "select", "find", "pull"}
WRITE_HINTS = {"set", "save", "write", "update", "insert", "delete", "post", "put", "commit", "store"}
EMIT_HINTS = {"emit", "publish", "send", "enqueue", "dispatch", "produce"}
ENTRYPOINT_HINTS = {"main", "cli", "handler", "endpoint", "serve", "run"}
ROUTE_HINTS = {"route", "get", "post", "put", "delete", "patch"}
AUTH_HINTS = {"auth", "oauth", "jwt", "token", "login", "permission"}
SECRET_HINTS = {"secret", "key", "token", "credential"}
PROTECTION_HINTS = {"encrypt", "decrypt", "hash", "sign", "verify"}
JAVA_PACKAGE_RE = re.compile(r"^\s*package\s+([A-Za-z_][\w.]*)\s*;", re.MULTILINE)
JAVA_IMPORT_RE = re.compile(r"^\s*import\s+(static\s+)?([A-Za-z_][\w.*]*)\s*;", re.MULTILINE)
JAVA_CLASS_RE = re.compile(r"\b(class|interface|enum|record)\s+([A-Za-z_][A-Za-z0-9_]*)")
JAVA_METHOD_RE = re.compile(
    r"^\s*(?:(public|protected|private)\s+)?"
    r"(?:(static)\s+)?"
    r"(?:(final|abstract|synchronized|native|default)\s+)*"
    r"(?:<[^>]+>\s+)?"
    r"[\w<>\[\], ?]+\s+([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*(?:throws [^{]+)?\{"
)
JAVA_CALL_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_\.]*)\s*\(")
JAVA_METHOD_EXCLUDE = {
    "if",
    "for",
    "while",
    "switch",
    "catch",
    "return",
    "new",
    "throw",
    "else",
    "do",
    "try",
    "synchronized",
    "assert",
}


@dataclass(slots=True)
class ModuleContext:
    module_name: str
    path: Path
    package_name: str
    internal_imports: set[str]
    external_imports: set[str]
    call_names: set[str]
    public_symbols: list[str]
    decorators: set[str]
    entrypoint: bool
    data_targets: dict[str, str]
    has_read_behavior: bool
    has_write_behavior: bool
    has_emit_behavior: bool
    has_observability: bool
    has_auth: bool
    has_secret_handling: bool
    has_data_protection: bool


@dataclass(slots=True)
class FunctionContext:
    qualified_name: str
    module_name: str
    path: Path
    kind: str
    public: bool
    class_name: str | None
    decorators: list[str]
    raw_calls: set[str]
    entrypoint: bool
    statement_count: int


@dataclass(slots=True)
class FunctionModuleContext:
    module_name: str
    path: Path
    module_aliases: dict[str, str]
    symbol_aliases: dict[str, str]
    class_methods: dict[str, set[str]]
    functions: list[FunctionContext]


def _module_name_from_path(path: Path) -> str:
    without_suffix = path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _java_module_name(path: Path, package_name: str | None) -> str:
    stem = path.stem
    return f"{package_name}.{stem}" if package_name else stem


def discover_python_modules(repo_root: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in repo_root.rglob("*.py"):
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        rel = path.relative_to(repo_root)
        module_name = _module_name_from_path(rel)
        if module_name:
            modules[module_name] = path
    return dict(sorted(modules.items()))


def discover_java_modules(repo_root: Path) -> dict[str, Path]:
    modules: dict[str, Path] = {}
    for path in repo_root.rglob("*.java"):
        if ".git" in path.parts:
            continue
        package_name = _read_java_package(path)
        module_name = _java_module_name(path.relative_to(repo_root), package_name)
        modules[module_name] = path
    return dict(sorted(modules.items()))


def _read_java_package(path: Path) -> str | None:
    match = JAVA_PACKAGE_RE.search(path.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def _resolve_import(current_module: str, level: int, module: str | None) -> str | None:
    if level == 0:
        return module
    parts = current_module.split(".")
    if current_module and parts:
        parts = parts[:-1]
    if level > 1:
        parts = parts[: max(0, len(parts) - (level - 1))]
    if module:
        parts.extend(module.split("."))
    return ".".join(part for part in parts if part)


def _longest_internal_match(import_name: str, module_names: set[str]) -> str | None:
    parts = import_name.split(".")
    for index in range(len(parts), 0, -1):
        candidate = ".".join(parts[:index])
        if candidate in module_names:
            return candidate
    return None


def _call_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return None


def _decorator_name(node: ast.AST) -> str | None:
    return _call_name(node)


def _package_name(module_name: str) -> str:
    return module_name.split(".", 1)[0] if "." in module_name else module_name


def scan_python_repository(repo_root: Path) -> dict[str, ModuleContext]:
    modules = discover_python_modules(repo_root)
    module_names = set(modules)
    contexts: dict[str, ModuleContext] = {}

    for module_name, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        internal: set[str] = set()
        external: set[str] = set()
        call_names: set[str] = set()
        public_symbols: list[str] = []
        decorators: set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    internal_target = _longest_internal_match(target, module_names)
                    if internal_target:
                        internal.add(internal_target)
                    else:
                        external.add(target.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_import(module_name, node.level, node.module)
                for alias in node.names:
                    if alias.name == "*":
                        if base:
                            internal_target = _longest_internal_match(base, module_names)
                            if internal_target:
                                internal.add(internal_target)
                            else:
                                external.add(base.split(".")[0])
                        continue
                    candidate = f"{base}.{alias.name}" if base else alias.name
                    internal_target = _longest_internal_match(candidate, module_names)
                    if internal_target:
                        internal.add(internal_target)
                    elif base:
                        external.add(base.split(".")[0])
            elif isinstance(node, ast.Call):
                name = _call_name(node.func)
                if name:
                    call_names.add(name)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if not node.name.startswith("_"):
                    public_symbols.append(node.name)
                for decorator in node.decorator_list:
                    name = _decorator_name(decorator)
                    if name:
                        decorators.add(name)

        lower_calls = {name.lower() for name in call_names}
        lower_decorators = {name.lower() for name in decorators}
        lower_externals = {name.lower() for name in external}

        data_targets: dict[str, str] = {}
        for name in external:
            lower = name.lower()
            if lower in DATA_STORE_IMPORTS:
                data_targets[name] = DATA_STORE_IMPORTS[lower]
            elif lower in QUEUE_IMPORTS:
                data_targets[name] = QUEUE_IMPORTS[lower]
            elif lower in EXTERNAL_SERVICE_IMPORTS:
                data_targets[name] = EXTERNAL_SERVICE_IMPORTS[lower]

        entrypoint = (
            path.name in {"main.py", "app.py", "cli.py", "routes.py", "views.py", "api.py"}
            or any(hint in symbol.lower() for symbol in public_symbols for hint in ENTRYPOINT_HINTS)
            or any(hint in decorator for decorator in lower_decorators for hint in ROUTE_HINTS)
        )
        has_read_behavior = any(any(hint in name for hint in READ_HINTS) for name in lower_calls)
        has_write_behavior = any(any(hint in name for hint in WRITE_HINTS) for name in lower_calls)
        has_emit_behavior = any(any(hint in name for hint in EMIT_HINTS) for name in lower_calls)
        has_observability = bool(lower_externals & OBSERVABILITY_IMPORTS) or any(
            "log" in name or "metric" in name or "trace" in name for name in lower_calls
        )
        has_auth = bool(lower_externals & SECURITY_IMPORTS) or any(any(hint in name for hint in AUTH_HINTS) for name in lower_calls)
        has_secret_handling = any(any(hint in name for hint in SECRET_HINTS) for name in lower_calls)
        has_data_protection = any(any(hint in name for hint in PROTECTION_HINTS) for name in lower_calls)

        contexts[module_name] = ModuleContext(
            module_name=module_name,
            path=path,
            package_name=_package_name(module_name),
            internal_imports=internal,
            external_imports=external,
            call_names=call_names,
            public_symbols=sorted(public_symbols),
            decorators=decorators,
            entrypoint=entrypoint,
            data_targets=data_targets,
            has_read_behavior=has_read_behavior,
            has_write_behavior=has_write_behavior,
            has_emit_behavior=has_emit_behavior,
            has_observability=has_observability,
            has_auth=has_auth,
            has_secret_handling=has_secret_handling,
            has_data_protection=has_data_protection,
        )

    return contexts


def scan_java_repository(repo_root: Path) -> dict[str, ModuleContext]:
    modules = discover_java_modules(repo_root)
    module_names = set(modules)
    contexts: dict[str, ModuleContext] = {}

    for module_name, path in modules.items():
        source = path.read_text(encoding="utf-8")
        package_name = _read_java_package(path) or module_name.rsplit(".", 1)[0]
        imports = JAVA_IMPORT_RE.findall(source)
        internal: set[str] = set()
        external: set[str] = set()
        decorators: set[str] = set()
        public_symbols = sorted({match.group(2) for match in JAVA_CLASS_RE.finditer(source)})

        for static_prefix, import_name in imports:
            if import_name.endswith(".*"):
                base_import = import_name[:-2]
                internal_match = _longest_internal_match(base_import, module_names)
            else:
                internal_match = _longest_internal_match(import_name, module_names)
            if internal_match:
                internal.add(internal_match)
            else:
                external.add(import_name.split(".")[0])

        call_names = _collect_java_calls(source)
        lower_calls = {name.lower() for name in call_names}
        lower_externals = {name.lower() for name in external}

        data_targets: dict[str, str] = {}
        for name in external:
            lower = name.lower()
            if lower in DATA_STORE_IMPORTS:
                data_targets[name] = DATA_STORE_IMPORTS[lower]
            elif lower in QUEUE_IMPORTS:
                data_targets[name] = QUEUE_IMPORTS[lower]
            elif lower in EXTERNAL_SERVICE_IMPORTS:
                data_targets[name] = EXTERNAL_SERVICE_IMPORTS[lower]

        entrypoint = path.name in {"Main.java", "Application.java", "App.java"} or "main" in lower_calls
        has_read_behavior = any(any(hint in name for hint in READ_HINTS) for name in lower_calls)
        has_write_behavior = any(any(hint in name for hint in WRITE_HINTS) for name in lower_calls)
        has_emit_behavior = any(any(hint in name for hint in EMIT_HINTS) for name in lower_calls)
        has_observability = bool(lower_externals & OBSERVABILITY_IMPORTS) or any(
            "log" in name or "metric" in name or "trace" in name for name in lower_calls
        )
        has_auth = bool(lower_externals & SECURITY_IMPORTS) or any(any(hint in name for hint in AUTH_HINTS) for name in lower_calls)
        has_secret_handling = any(any(hint in name for hint in SECRET_HINTS) for name in lower_calls)
        has_data_protection = any(any(hint in name for hint in PROTECTION_HINTS) for name in lower_calls)

        contexts[module_name] = ModuleContext(
            module_name=module_name,
            path=path,
            package_name=package_name,
            internal_imports=internal,
            external_imports=external,
            call_names=call_names,
            public_symbols=public_symbols,
            decorators=decorators,
            entrypoint=entrypoint,
            data_targets=data_targets,
            has_read_behavior=has_read_behavior,
            has_write_behavior=has_write_behavior,
            has_emit_behavior=has_emit_behavior,
            has_observability=has_observability,
            has_auth=has_auth,
            has_secret_handling=has_secret_handling,
            has_data_protection=has_data_protection,
        )

    return contexts


def scan_python_functions(repo_root: Path) -> dict[str, FunctionModuleContext]:
    modules = discover_python_modules(repo_root)
    module_names = set(modules)
    function_modules: dict[str, FunctionModuleContext] = {}

    for module_name, path in modules.items():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        module_aliases: dict[str, str] = {}
        symbol_aliases: dict[str, str] = {}
        class_methods: dict[str, set[str]] = defaultdict(set)
        functions: list[FunctionContext] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    target = alias.name
                    internal_target = _longest_internal_match(target, module_names)
                    if internal_target:
                        alias_name = alias.asname or alias.name.split(".")[0]
                        module_aliases[alias_name] = internal_target
            elif isinstance(node, ast.ImportFrom):
                base = _resolve_import(module_name, node.level, node.module)
                base_module = _longest_internal_match(base, module_names) if base else None
                for alias in node.names:
                    if alias.name == "*":
                        continue
                    candidate = f"{base}.{alias.name}" if base else alias.name
                    internal_target = _longest_internal_match(candidate, module_names)
                    alias_name = alias.asname or alias.name
                    if internal_target:
                        module_aliases[alias_name] = internal_target
                    elif base_module:
                        symbol_aliases[alias_name] = f"{base_module}.{alias.name}"

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                functions.append(_build_function_context(module_name, path, node))
            elif isinstance(node, ast.ClassDef):
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        class_methods[node.name].add(child.name)
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        functions.append(_build_function_context(module_name, path, child, class_name=node.name))

        function_modules[module_name] = FunctionModuleContext(
            module_name=module_name,
            path=path,
            module_aliases=dict(sorted(module_aliases.items())),
            symbol_aliases=dict(sorted(symbol_aliases.items())),
            class_methods={name: set(sorted(methods)) for name, methods in sorted(class_methods.items())},
            functions=functions,
        )

    return function_modules


def scan_java_functions(repo_root: Path) -> dict[str, FunctionModuleContext]:
    modules = discover_java_modules(repo_root)
    module_names = set(modules)
    function_modules: dict[str, FunctionModuleContext] = {}

    for module_name, path in modules.items():
        source = path.read_text(encoding="utf-8")
        module_aliases: dict[str, str] = {}
        symbol_aliases: dict[str, str] = {}
        class_methods: dict[str, set[str]] = defaultdict(set)
        functions: list[FunctionContext] = []

        for static_prefix, import_name in JAVA_IMPORT_RE.findall(source):
            import_is_static = bool(static_prefix.strip())
            if import_name.endswith(".*"):
                base_import = import_name[:-2]
                internal_target = _longest_internal_match(base_import, module_names)
                if internal_target:
                    module_aliases[base_import.split(".")[-1]] = internal_target
                continue
            internal_target = _longest_internal_match(import_name, module_names)
            alias_name = import_name.split(".")[-1]
            if internal_target:
                module_aliases[alias_name] = internal_target
            elif import_is_static:
                owning_module = _longest_internal_match(import_name.rsplit(".", 1)[0], module_names)
                if owning_module:
                    symbol_aliases[alias_name] = f"{owning_module}.{alias_name}"

        class_name = path.stem
        class_match = JAVA_CLASS_RE.search(source)
        if class_match:
            class_name = class_match.group(2)

        for method in _extract_java_methods(source):
            class_methods[class_name].add(method["name"])
            functions.append(
                FunctionContext(
                    qualified_name=f"{module_name}.{method['name']}",
                    module_name=module_name,
                    path=path,
                    kind="method",
                    public=method["public"],
                    class_name=class_name,
                    decorators=[],
                    raw_calls=method["calls"],
                    entrypoint=method["name"].lower() == "main" or any(
                        hint in method["name"].lower() for hint in ENTRYPOINT_HINTS
                    ),
                    statement_count=method["statement_count"],
                )
            )

        function_modules[module_name] = FunctionModuleContext(
            module_name=module_name,
            path=path,
            module_aliases=dict(sorted(module_aliases.items())),
            symbol_aliases=dict(sorted(symbol_aliases.items())),
            class_methods={name: set(sorted(methods)) for name, methods in sorted(class_methods.items())},
            functions=functions,
        )

    return function_modules


def _collect_java_calls(source: str) -> set[str]:
    calls = set()
    for match in JAVA_CALL_RE.finditer(source):
        name = match.group(1)
        if name.split(".")[0] in JAVA_METHOD_EXCLUDE:
            continue
        calls.add(name)
    return calls


def _extract_java_methods(source: str) -> list[dict[str, Any]]:
    methods: list[dict[str, Any]] = []
    lines = source.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        match = JAVA_METHOD_RE.match(line)
        if not match:
            index += 1
            continue
        method_name = match.group(4)
        if method_name in JAVA_METHOD_EXCLUDE:
            index += 1
            continue
        body_lines = [line]
        brace_depth = line.count("{") - line.count("}")
        index += 1
        while index < len(lines) and brace_depth > 0:
            body_lines.append(lines[index])
            brace_depth += lines[index].count("{") - lines[index].count("}")
            index += 1
        body = "\n".join(body_lines)
        methods.append(
            {
                "name": method_name,
                "public": match.group(1) == "public",
                "calls": _collect_java_calls(body),
                "statement_count": max(1, sum(line.count(";") for line in body_lines)),
            }
        )
    return methods


def _build_function_context(
    module_name: str,
    path: Path,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    class_name: str | None = None,
) -> FunctionContext:
    decorators = sorted(name for decorator in node.decorator_list if (name := _decorator_name(decorator)))
    qualified_name = f"{module_name}.{node.name}" if class_name is None else f"{module_name}.{class_name}.{node.name}"
    entrypoint = (
        any(hint in node.name.lower() for hint in ENTRYPOINT_HINTS)
        or any(any(hint in decorator.lower() for hint in ROUTE_HINTS | ENTRYPOINT_HINTS) for decorator in decorators)
    )
    statement_count = sum(1 for child in ast.walk(node) if isinstance(child, ast.stmt))
    return FunctionContext(
        qualified_name=qualified_name,
        module_name=module_name,
        path=path,
        kind="method" if class_name else "function",
        public=not node.name.startswith("_"),
        class_name=class_name,
        decorators=decorators,
        raw_calls=_collect_calls(node.body),
        entrypoint=entrypoint,
        statement_count=statement_count,
    )


def _collect_calls(body: list[ast.stmt]) -> set[str]:
    calls: set[str] = set()

    def visit(node: ast.AST) -> None:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            return
        if isinstance(node, ast.Call):
            name = _call_name(node.func)
            if name:
                calls.add(name)
        for child in ast.iter_child_nodes(node):
            visit(child)

    for statement in body:
        visit(statement)
    return calls


def build_graph_bundle(
    snapshot: RepositorySnapshot,
    repo_root: Path,
) -> tuple[dict[str, ArchitectureGraph], dict[str, dict[str, Any]], dict[str, Any]]:
    contexts = {}
    contexts.update(scan_python_repository(repo_root))
    contexts.update(scan_java_repository(repo_root))
    function_contexts = {}
    function_contexts.update(scan_python_functions(repo_root))
    function_contexts.update(scan_java_functions(repo_root))
    graphs = {
        "dependency_graph": build_dependency_graph(snapshot, repo_root, contexts),
        "architecture_graph": build_architecture_graph(snapshot, repo_root, contexts),
        "data_flow_graph": build_data_flow_graph(snapshot, repo_root, contexts),
        "interface_graph": build_interface_graph(snapshot, repo_root, contexts),
        "function_graph": build_function_graph(snapshot, repo_root, function_contexts),
        "operational_risk_graph": build_operational_risk_graph(snapshot, repo_root, contexts),
    }
    feature_schemas = {graph_id: feature_schema_for_graph(graph) for graph_id, graph in graphs.items()}
    inventory = module_inventory(contexts, function_contexts, repo_root)
    return graphs, feature_schemas, inventory


def module_inventory(
    contexts: dict[str, ModuleContext],
    function_contexts: dict[str, FunctionModuleContext],
    repo_root: Path,
) -> dict[str, Any]:
    return {
        "modules": {
            module_name: {
                "path": compact_path(context.path, repo_root),
                "package": context.package_name,
                "internal_imports": sorted(context.internal_imports),
                "external_imports": sorted(context.external_imports),
                "public_symbols": context.public_symbols,
                "function_count": len(function_contexts.get(module_name, _empty_function_module(module_name, context.path)).functions),
                "entrypoint": context.entrypoint,
                "data_targets": context.data_targets,
            }
            for module_name, context in sorted(contexts.items())
        },
        "functions": {
            module_name: [
                {
                    "qualified_name": function.qualified_name,
                    "kind": function.kind,
                    "public": function.public,
                    "entrypoint": function.entrypoint,
                    "statement_count": function.statement_count,
                }
                for function in function_module.functions
            ]
            for module_name, function_module in sorted(function_contexts.items())
        },
    }


def _empty_function_module(module_name: str, path: Path) -> FunctionModuleContext:
    return FunctionModuleContext(
        module_name=module_name,
        path=path,
        module_aliases={},
        symbol_aliases={},
        class_methods={},
        functions=[],
    )


def build_dependency_graph(
    snapshot: RepositorySnapshot,
    repo_root: Path,
    contexts: dict[str, ModuleContext],
) -> ArchitectureGraph:
    nodes: list[GraphNode] = [
        GraphNode(
            id="repository:root",
            type="repository",
            label=Path(snapshot.root_path).name,
            metadata={"branch": snapshot.branch, "commit_sha": snapshot.commit_sha},
        )
    ]
    edges: list[GraphEdge] = []
    external_nodes: dict[str, GraphNode] = {}

    for module_name, context in sorted(contexts.items()):
        rel = compact_path(context.path, repo_root)
        nodes.append(
            GraphNode(
                id=f"module:{module_name}",
                type="module",
                label=module_name,
                metadata={
                    "path": rel,
                    "path_depth": len(module_name.split(".")),
                    "internal_import_count": len(context.internal_imports),
                    "external_import_count": len(context.external_imports),
                },
            )
        )
        edges.append(GraphEdge("repository:root", f"module:{module_name}", "contains", {"path": rel}))
        for target in sorted(context.internal_imports):
            edges.append(GraphEdge(f"module:{module_name}", f"module:{target}", "imports", {}))
        for dependency in sorted(context.external_imports):
            external_id = f"external:{dependency}"
            if external_id not in external_nodes:
                external_nodes[external_id] = GraphNode(
                    id=external_id,
                    type="external_dependency",
                    label=dependency,
                    metadata={"top_level_package": dependency},
                )
            edges.append(GraphEdge(f"module:{module_name}", external_id, "depends_on", {}))

    nodes.extend(external_nodes.values())
    return ArchitectureGraph(
        repository=snapshot.github_url,
        nodes=nodes,
        edges=edges,
        metadata={
            "graph_id": "dependency_graph",
            "title": "Dependency Graph",
            "module_count": len(contexts),
            "external_dependency_count": len(external_nodes),
        },
    )


def build_architecture_graph(
    snapshot: RepositorySnapshot,
    repo_root: Path,
    contexts: dict[str, ModuleContext],
) -> ArchitectureGraph:
    nodes: list[GraphNode] = [
        GraphNode(
            id="repository:root",
            type="repository",
            label=Path(snapshot.root_path).name,
            metadata={"branch": snapshot.branch, "commit_sha": snapshot.commit_sha},
        )
    ]
    edges: list[GraphEdge] = []

    package_to_modules: dict[str, list[str]] = defaultdict(list)
    for module_name, context in contexts.items():
        package_to_modules[context.package_name].append(module_name)

    for package_name, modules in sorted(package_to_modules.items()):
        nodes.append(
            GraphNode(
                id=f"package:{package_name}",
                type="package",
                label=package_name,
                metadata={"module_count": len(modules)},
            )
        )
        edges.append(GraphEdge("repository:root", f"package:{package_name}", "contains", {}))

    package_edges: set[tuple[str, str]] = set()
    for module_name, context in sorted(contexts.items()):
        module_id = f"module:{module_name}"
        nodes.append(
            GraphNode(
                id=module_id,
                type="module",
                label=module_name,
                metadata={"package": context.package_name, "path": compact_path(context.path, repo_root)},
            )
        )
        edges.append(GraphEdge(f"package:{context.package_name}", module_id, "contains", {}))
        for target in sorted(context.internal_imports):
            target_package = contexts[target].package_name
            if target_package != context.package_name:
                package_edges.add((context.package_name, target_package))

    for source_package, target_package in sorted(package_edges):
        edges.append(
            GraphEdge(
                f"package:{source_package}",
                f"package:{target_package}",
                "depends_on",
                {"cross_package": True},
            )
        )

    return ArchitectureGraph(
        repository=snapshot.github_url,
        nodes=nodes,
        edges=edges,
        metadata={
            "graph_id": "architecture_graph",
            "title": "Architecture Graph",
            "package_count": len(package_to_modules),
            "cross_package_dependency_count": len(package_edges),
        },
    )


def build_data_flow_graph(
    snapshot: RepositorySnapshot,
    repo_root: Path,
    contexts: dict[str, ModuleContext],
) -> ArchitectureGraph:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    target_nodes: dict[str, GraphNode] = {}

    for module_name, context in sorted(contexts.items()):
        module_id = f"module:{module_name}"
        nodes.append(
            GraphNode(
                id=module_id,
                type="module",
                label=module_name,
                metadata={"path": compact_path(context.path, repo_root)},
            )
        )
        for target_name, target_type in sorted(context.data_targets.items()):
            node_id = f"{target_type}:{target_name}"
            if node_id not in target_nodes:
                target_nodes[node_id] = GraphNode(
                    id=node_id,
                    type=target_type,
                    label=target_name,
                    metadata={"inferred": True},
                )
            if context.has_read_behavior:
                edges.append(GraphEdge(module_id, node_id, "reads_from", {}))
            if context.has_write_behavior:
                edges.append(GraphEdge(module_id, node_id, "writes_to", {}))
            if context.has_emit_behavior:
                edges.append(GraphEdge(module_id, node_id, "emits_to", {}))
            if not (context.has_read_behavior or context.has_write_behavior or context.has_emit_behavior):
                edges.append(GraphEdge(module_id, node_id, "uses", {}))

    nodes.extend(target_nodes.values())
    return ArchitectureGraph(
        repository=snapshot.github_url,
        nodes=nodes,
        edges=edges,
        metadata={
            "graph_id": "data_flow_graph",
            "title": "Data Flow Graph",
            "target_count": len(target_nodes),
        },
    )


def build_interface_graph(
    snapshot: RepositorySnapshot,
    repo_root: Path,
    contexts: dict[str, ModuleContext],
) -> ArchitectureGraph:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    interface_nodes: set[str] = set()

    for module_name, context in sorted(contexts.items()):
        module_id = f"module:{module_name}"
        nodes.append(
            GraphNode(
                id=module_id,
                type="module",
                label=module_name,
                metadata={"path": compact_path(context.path, repo_root)},
            )
        )
        interface_id = f"interface:{module_name}"
        interface_nodes.add(interface_id)
        nodes.append(
            GraphNode(
                id=interface_id,
                type="api",
                label=module_name,
                metadata={
                    "public_symbol_count": len(context.public_symbols),
                    "entrypoint": context.entrypoint,
                },
            )
        )
        edges.append(GraphEdge(module_id, interface_id, "implements", {}))
        if context.entrypoint:
            entrypoint_id = f"entrypoint:{module_name}"
            nodes.append(
                GraphNode(
                    id=entrypoint_id,
                    type="entrypoint",
                    label=module_name,
                    metadata={"path": compact_path(context.path, repo_root)},
                )
            )
            edges.append(GraphEdge(entrypoint_id, interface_id, "calls", {"entrypoint": True}))

    for module_name, context in sorted(contexts.items()):
        for target in sorted(context.internal_imports):
            target_interface = f"interface:{target}"
            if target_interface in interface_nodes:
                edges.append(GraphEdge(f"module:{module_name}", target_interface, "calls", {}))

    return ArchitectureGraph(
        repository=snapshot.github_url,
        nodes=nodes,
        edges=edges,
        metadata={
            "graph_id": "interface_graph",
            "title": "Interface Graph",
            "interface_count": len(interface_nodes),
        },
    )


def build_function_graph(
    snapshot: RepositorySnapshot,
    repo_root: Path,
    function_modules: dict[str, FunctionModuleContext],
) -> ArchitectureGraph:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    function_ids = {
        function.qualified_name
        for function_module in function_modules.values()
        for function in function_module.functions
    }

    for module_name, function_module in sorted(function_modules.items()):
        module_id = f"module:{module_name}"
        nodes.append(
            GraphNode(
                id=module_id,
                type="module",
                label=module_name,
                metadata={"path": compact_path(function_module.path, repo_root)},
            )
        )
        for function in function_module.functions:
            function_id = f"function:{function.qualified_name}"
            nodes.append(
                GraphNode(
                    id=function_id,
                    type="function",
                    label=function.qualified_name,
                    metadata={
                        "module": function.module_name,
                        "kind": function.kind,
                        "class_name": function.class_name,
                        "public": function.public,
                        "entrypoint": function.entrypoint,
                        "statement_count": function.statement_count,
                        "path": compact_path(function.path, repo_root),
                    },
                )
            )
            edges.append(GraphEdge(module_id, function_id, "contains", {}))
            for raw_call in sorted(function.raw_calls):
                target = _resolve_function_call(raw_call, function, function_module, function_ids)
                if target:
                    edges.append(GraphEdge(function_id, f"function:{target}", "calls", {"raw_call": raw_call}))

    return ArchitectureGraph(
        repository=snapshot.github_url,
        nodes=nodes,
        edges=edges,
        metadata={
            "graph_id": "function_graph",
            "title": "Function Relationship Graph",
            "function_count": len(function_ids),
            "module_count": len(function_modules),
        },
    )


def _resolve_function_call(
    raw_call: str,
    function: FunctionContext,
    function_module: FunctionModuleContext,
    function_ids: set[str],
) -> str | None:
    if raw_call in function_ids:
        return raw_call

    parts = raw_call.split(".")
    if not parts:
        return None

    first = parts[0]
    remainder = parts[1:]

    if len(parts) == 1:
        if function.class_name:
            for candidate in (f"{function.module_name}.{function.class_name}.{first}", f"{function.module_name}.{first}"):
                if candidate in function_ids:
                    return candidate
        candidate = f"{function.module_name}.{first}"
        if candidate in function_ids:
            return candidate
        alias_target = function_module.symbol_aliases.get(first)
        if alias_target in function_ids:
            return alias_target
        return None

    if first in {"self", "cls"} and function.class_name and remainder:
        for candidate in (f"{function.module_name}.{function.class_name}.{remainder[0]}", f"{function.module_name}.{remainder[0]}"):
            if candidate in function_ids:
                return candidate

    if first in function_module.module_aliases and remainder:
        imported_module = function_module.module_aliases[first]
        candidate = f"{imported_module}.{'.'.join(remainder)}"
        if candidate in function_ids:
            return candidate

    if first in function_module.symbol_aliases:
        base = function_module.symbol_aliases[first]
        candidate = f"{base}.{'.'.join(remainder)}" if remainder else base
        if candidate in function_ids:
            return candidate

    if len(parts) == 2 and parts[0] in function_module.class_methods:
        for candidate in (f"{function.module_name}.{parts[0]}.{parts[1]}", f"{function.module_name}.{parts[1]}"):
            if candidate in function_ids:
                return candidate

    candidate = f"{function.module_name}.{raw_call}"
    if candidate in function_ids:
        return candidate
    return None


def build_operational_risk_graph(
    snapshot: RepositorySnapshot,
    repo_root: Path,
    contexts: dict[str, ModuleContext],
) -> ArchitectureGraph:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    capability_nodes = {
        "capability:observability": ("metric", "observability"),
        "capability:authentication": ("security_capability", "authentication"),
        "capability:secret_handling": ("security_capability", "secret_handling"),
        "capability:data_protection": ("security_capability", "data_protection"),
    }

    for node_id, (node_type, label) in capability_nodes.items():
        nodes.append(GraphNode(node_id, node_type, label, {}))

    for module_name, context in sorted(contexts.items()):
        module_id = f"module:{module_name}"
        nodes.append(
            GraphNode(
                id=module_id,
                type="module",
                label=module_name,
                metadata={"path": compact_path(context.path, repo_root)},
            )
        )
        if context.has_observability:
            edges.append(GraphEdge(module_id, "capability:observability", "evaluated_by", {}))
        if context.has_auth:
            edges.append(GraphEdge(module_id, "capability:authentication", "uses", {}))
        if context.has_secret_handling:
            edges.append(GraphEdge(module_id, "capability:secret_handling", "uses", {}))
        if context.has_data_protection:
            edges.append(GraphEdge(module_id, "capability:data_protection", "uses", {}))

    return ArchitectureGraph(
        repository=snapshot.github_url,
        nodes=nodes,
        edges=edges,
        metadata={
            "graph_id": "operational_risk_graph",
            "title": "Operational Risk Graph",
            "module_count": len(contexts),
        },
    )


def feature_schema_for_graph(graph: ArchitectureGraph) -> dict[str, Any]:
    return {
        "graph_id": graph.metadata.get("graph_id"),
        "node_features": ["in_degree", "out_degree", "path_depth", "public_symbol_count"],
        "edge_types": sorted({edge.type for edge in graph.edges}),
        "schema_version": 1,
    }


def encode_pyg(graph: ArchitectureGraph) -> dict[str, Any]:
    node_index = {node.id: idx for idx, node in enumerate(graph.nodes)}
    in_degree = defaultdict(int)
    out_degree = defaultdict(int)
    for edge in graph.edges:
        out_degree[edge.source] += 1
        in_degree[edge.target] += 1

    features: dict[str, list[list[int]]] = defaultdict(list)
    node_ids_by_type: dict[str, list[str]] = defaultdict(list)
    node_offsets: dict[str, dict[str, int]] = defaultdict(dict)
    for node in graph.nodes:
        node_type = node.type
        node_offsets[node_type][node.id] = len(node_ids_by_type[node_type])
        node_ids_by_type[node_type].append(node.id)
        features[node_type].append(
            [
                int(node.metadata.get("path_depth", 0)),
                int(node.metadata.get("public_symbol_count", 0)),
                in_degree[node.id],
                out_degree[node.id],
            ]
        )

    edge_index: dict[str, list[list[int]]] = defaultdict(lambda: [[], []])
    for edge in graph.edges:
        src_type = next(node.type for node in graph.nodes if node.id == edge.source)
        dst_type = next(node.type for node in graph.nodes if node.id == edge.target)
        key = f"{src_type}::{edge.type}::{dst_type}"
        edge_index[key][0].append(node_offsets[src_type][edge.source])
        edge_index[key][1].append(node_offsets[dst_type][edge.target])

    payload = {
        "backend": "fallback-json",
        "graph_id": graph.metadata.get("graph_id"),
        "node_types": dict(node_ids_by_type),
        "features": dict(features),
        "edge_index": dict(edge_index),
    }

    try:  # pragma: no cover - optional dependency path
        import torch
        from torch_geometric.data import HeteroData

        data = HeteroData()
        for node_type, rows in features.items():
            data[node_type].x = torch.tensor(rows, dtype=torch.float32)
        for edge_key, indices in edge_index.items():
            src_type, edge_type, dst_type = edge_key.split("::")
            data[(src_type, edge_type, dst_type)].edge_index = torch.tensor(indices, dtype=torch.long)
        payload = data
    except Exception:
        pass

    return payload


def save_pyg_payload(payload: Any, path: Path) -> None:
    try:  # pragma: no cover - optional dependency path
        import torch
        from torch_geometric.data import HeteroData

        if payload.__class__.__name__ == "HeteroData":
            path.parent.mkdir(parents=True, exist_ok=True)
            torch.save(payload, path)
            return
    except Exception:
        pass
    write_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")
