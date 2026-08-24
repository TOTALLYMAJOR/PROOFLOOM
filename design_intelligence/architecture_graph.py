from __future__ import annotations

import ast
import fnmatch
import hashlib
import json
import re
import tomllib
from collections import deque
from pathlib import Path
from typing import Any, Iterable

from .storage import ensure_within, read_json, sha256_file


GRAPH_SCHEMA_VERSION = 1
DEFAULT_INCLUDE = [
    "app/**",
    "components/**",
    "pages/**",
    "src/**",
    "design_intelligence/**",
    "scripts/**",
    "tests/**",
    "*.json",
    "*.toml",
    "*.yaml",
]
DEFAULT_EXCLUDE = [
    ".git/**",
    ".venv/**",
    "node_modules/**",
    "artifacts/**",
    "**/__pycache__/**",
    "**/*.pyc",
]
SOURCE_SUFFIXES = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
SCHEMA_SUFFIXES = {".prisma", ".sql"}
JS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json")
HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
JS_IMPORT_RE = re.compile(
    r"(?:\bfrom\s+|\brequire\s*\(\s*|\bimport\s*\(\s*)['\"]([^'\"]+)['\"]"
)
JS_API_CALL_RE = re.compile(
    r"(?:fetch\s*\(\s*|axios\.(?:get|post|put|patch|delete)\s*\(\s*)['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
DECORATOR_API_RE = re.compile(
    r"@(?:app|router)\.(get|post|put|patch|delete|options|head)\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)
EXPRESS_API_RE = re.compile(
    r"(?:app|router)\.(get|post|put|patch|delete|options|head)\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def build_architecture_graph(
    repository_root: str | Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    config = _graph_config(manifest)
    if not config.get("enabled", False):
        return _empty_graph(root, "DISABLED", ["Architecture impact graph is disabled"])

    errors: list[str] = []
    warnings: list[str] = []
    candidates = _source_files(root, config, errors)
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    path_nodes: dict[str, str] = {}

    for relative in candidates:
        target = ensure_within(root, relative)
        node_type = _path_node_type(relative)
        node_id = _node_id(node_type, relative)
        node = {
            "id": node_id,
            "type": node_type,
            "label": relative,
            "path": relative,
            "sha256": sha256_file(target),
        }
        if target.suffix.lower() in SOURCE_SUFFIXES:
            node["language"] = _language(target.suffix.lower())
        nodes[node_id] = node
        path_nodes[relative] = node_id

    _add_repository_packages(root, candidates, nodes, edges)
    _add_import_edges(root, path_nodes, nodes, edges, errors, warnings)
    _add_api_nodes(root, path_nodes, nodes, edges, warnings)
    _add_schema_usage_edges(root, path_nodes, nodes, edges)
    _add_intent_nodes(root, manifest, config, path_nodes, nodes, edges, errors)
    _add_ownership_nodes(root, config, path_nodes, nodes, edges, errors)
    _add_security_nodes(config, path_nodes, nodes, edges, errors)

    max_nodes = config.get("maxNodes", 5000)
    discovered_node_count = len(nodes)
    truncated = discovered_node_count > max_nodes
    if truncated:
        errors.append(
            f"Architecture graph has {discovered_node_count} nodes, exceeding maxNodes={max_nodes}; graph is incomplete"
        )

    ordered_nodes = sorted(nodes.values(), key=lambda item: item["id"])[:max_nodes]
    retained_ids = {node["id"] for node in ordered_nodes}
    ordered_edges = sorted(
        (
            edge
            for edge in edges.values()
            if edge["source"] in retained_ids and edge["target"] in retained_ids
        ),
        key=lambda item: (item["source"], item["type"], item["target"]),
    )
    digest = _digest({"nodes": ordered_nodes, "edges": ordered_edges})
    counts: dict[str, int] = {}
    for node in ordered_nodes:
        counts[node["type"]] = counts.get(node["type"], 0) + 1
    return {
        "schemaVersion": GRAPH_SCHEMA_VERSION,
        "status": "FAIL" if errors else "PASS",
        "root": str(root),
        "bounded": True,
        "limits": {
            "maxSourceFiles": config.get("maxSourceFiles", 2000),
            "maxNodes": max_nodes,
            "maxImpactNodes": config.get("maxImpactNodes", 300),
            "maxDepth": config.get("maxDepth", 4),
        },
        "sourceFilesScanned": len(candidates),
        "discoveredNodeCount": discovered_node_count,
        "nodeCount": len(ordered_nodes),
        "edgeCount": len(ordered_edges),
        "nodeCounts": dict(sorted(counts.items())),
        "nodes": ordered_nodes,
        "edges": ordered_edges,
        "graphSha256": digest,
        "truncated": truncated,
        "claimBoundary": (
            "Static repository evidence only; the graph does not prove runtime calls, approve boundary "
            "changes, or replace repository architecture authorities."
        ),
        "errors": errors,
        "warnings": sorted(set(warnings)),
    }


def analyze_architecture_impact(
    repository_root: str | Path,
    manifest: dict[str, Any],
    task: dict[str, Any],
    *,
    changed_paths: list[str] | None = None,
    graph: dict[str, Any] | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    config = _graph_config(manifest)
    graph = graph or build_architecture_graph(root, manifest)
    if graph.get("status") != "PASS":
        return {
            "status": "FAIL",
            "taskId": task.get("id"),
            "bounded": True,
            "truncated": bool(graph.get("truncated")),
            "errors": ["Architecture graph is not complete"] + list(graph.get("errors", [])),
            "warnings": graph.get("warnings", []),
            "graphSha256": graph.get("graphSha256"),
            "impactedNodes": [],
            "impactedPaths": [],
        }

    selected_paths = list(changed_paths or task.get("scope", {}).get("paths", []))
    path_nodes = {
        node.get("path"): node["id"]
        for node in graph["nodes"]
        if isinstance(node.get("path"), str)
    }
    nodes_by_id = {node["id"]: node for node in graph["nodes"]}
    seed_reasons: dict[str, set[str]] = {}
    unmatched: list[str] = []
    for pattern in selected_paths:
        matches = [
            node_id for path, node_id in path_nodes.items() if _matches(path, [pattern])
        ]
        if not matches:
            unmatched.append(pattern)
        for node_id in matches:
            seed_reasons.setdefault(node_id, set()).add(f"changed path matched {pattern}")

    task_journeys = task.get("intent", {}).get("journeys", [])
    # Journey nodes become traversal seeds only when no source path is represented.
    # Otherwise a journey would act as a hub and turn a small code change into a full-repository impact.
    if not seed_reasons:
        for journey_id in task_journeys:
            node_id = _node_id("journey", journey_id)
            if node_id in nodes_by_id:
                seed_reasons.setdefault(node_id, set()).add("required by task intent")

    propagation_types = {"imports", "calls-api", "uses-schema"}
    task_context_types = {"implemented-by", "verified-by"}
    adjacency: dict[str, list[tuple[str, dict[str, Any], str]]] = {}
    for edge in graph["edges"]:
        edge_type = edge["type"]
        if edge_type in propagation_types:
            if edge_type == "imports" and (
                nodes_by_id[edge["source"]]["type"] == "package"
                or nodes_by_id[edge["target"]]["type"] == "package"
            ):
                continue
            adjacency.setdefault(edge["target"], []).append((edge["source"], edge, "dependent"))
        elif edge_type in task_context_types:
            adjacency.setdefault(edge["source"], []).append((edge["target"], edge, "intent-binding"))
            adjacency.setdefault(edge["target"], []).append((edge["source"], edge, "intent-binding"))
        elif edge_type == "exposes-api":
            adjacency.setdefault(edge["source"], []).append((edge["target"], edge, "exposed-contract"))
            adjacency.setdefault(edge["target"], []).append((edge["source"], edge, "implementation"))

    max_depth = config.get("maxDepth", 4)
    max_impact_nodes = config.get("maxImpactNodes", 300)
    visited: dict[str, int] = {}
    reasons: dict[str, set[str]] = {key: set(value) for key, value in seed_reasons.items()}
    queue: deque[tuple[str, int]] = deque((node_id, 0) for node_id in sorted(seed_reasons))
    traversed_edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    truncated = False

    while queue:
        node_id, depth = queue.popleft()
        if node_id in visited and visited[node_id] <= depth:
            continue
        if len(visited) >= max_impact_nodes:
            truncated = True
            break
        visited[node_id] = depth
        if depth >= max_depth:
            continue
        if nodes_by_id[node_id]["type"] == "journey" and node_id not in seed_reasons:
            continue
        for target, edge, direction in sorted(
            adjacency.get(node_id, []), key=lambda item: (item[0], item[1]["type"])
        ):
            traversed_edges[(edge["source"], edge["type"], edge["target"])] = edge
            reasons.setdefault(target, set()).add(
                f"{direction} via {edge['type']} from {nodes_by_id[node_id]['label']}"
            )
            if target not in visited:
                queue.append((target, depth + 1))

    context_edges = {
        "owned-by": "owners",
        "governed-by": "securityBoundaries",
        "belongs-to-package": "packages",
        "exposes-api": "apis",
    }
    contextual: dict[str, set[str]] = {value: set() for value in context_edges.values()}
    for edge in graph["edges"]:
        category = context_edges.get(edge["type"])
        if not category:
            continue
        if edge["source"] in visited:
            contextual[category].add(edge["target"])
            traversed_edges[(edge["source"], edge["type"], edge["target"])] = edge
        elif edge["target"] in visited:
            contextual[category].add(edge["source"])
            traversed_edges[(edge["source"], edge["type"], edge["target"])] = edge

    impacted_ids = set(visited)
    for values in contextual.values():
        impacted_ids.update(values)
    impacted_nodes = []
    for node_id in sorted(impacted_ids):
        node = nodes_by_id[node_id]
        impacted_nodes.append({
            **node,
            "depth": visited.get(node_id),
            "reasons": sorted(reasons.get(node_id, {"attached architecture context"})),
        })

    security_nodes = [nodes_by_id[item] for item in sorted(contextual["securityBoundaries"])]
    required_checks = sorted({
        check
        for node in security_nodes
        for check in node.get("checks", [])
        if isinstance(check, str)
    })
    impacted_paths = sorted({
        node["path"] for node in impacted_nodes if isinstance(node.get("path"), str)
    })
    errors = []
    if truncated:
        errors.append(
            f"Impact traversal exceeded maxImpactNodes={max_impact_nodes}; analysis is incomplete"
        )
    warnings = list(graph.get("warnings", []))
    if unmatched:
        warnings.append(
            "Changed paths not represented in the static graph: " + ", ".join(sorted(unmatched))
        )
    return {
        "schemaVersion": GRAPH_SCHEMA_VERSION,
        "status": "FAIL" if errors else "PASS",
        "taskId": task.get("id"),
        "bounded": True,
        "limits": {"maxDepth": max_depth, "maxImpactNodes": max_impact_nodes},
        "seeds": [
            {"nodeId": node_id, "reasons": sorted(seed_reasons[node_id])}
            for node_id in sorted(seed_reasons)
        ],
        "changedPaths": selected_paths,
        "unmatchedPaths": sorted(unmatched),
        "impactedNodeCount": len(impacted_nodes),
        "impactedNodes": impacted_nodes,
        "impactedPaths": impacted_paths,
        "edges": sorted(
            traversed_edges.values(),
            key=lambda item: (item["source"], item["type"], item["target"]),
        ),
        "owners": _context_records(contextual["owners"], nodes_by_id),
        "securityBoundaries": _context_records(contextual["securityBoundaries"], nodes_by_id),
        "packages": _context_records(contextual["packages"], nodes_by_id),
        "apis": _context_records(contextual["apis"], nodes_by_id),
        "schemas": [node for node in impacted_nodes if node["type"] == "schema"],
        "journeys": [node for node in impacted_nodes if node["type"] == "journey"],
        "tests": [node for node in impacted_nodes if node["type"] == "test"],
        "requiredChecks": required_checks,
        "graphSha256": graph["graphSha256"],
        "truncated": truncated,
        "authorityRequired": bool(security_nodes),
        "claimBoundary": (
            "Impact is a bounded static recommendation. Protected boundary changes still require the "
            "declared human authority and successful repository verification."
        ),
        "errors": errors,
        "warnings": sorted(set(warnings)),
    }


def _source_files(root: Path, config: dict[str, Any], errors: list[str]) -> list[str]:
    include = config.get("include", DEFAULT_INCLUDE)
    exclude = config.get("exclude", DEFAULT_EXCLUDE)
    max_files = config.get("maxSourceFiles", 2000)
    matches: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(root).as_posix()
        if _matches(relative, exclude) or not _matches(relative, include):
            continue
        matches.append(relative)
    if len(matches) > max_files:
        errors.append(
            f"Architecture graph matched {len(matches)} files, exceeding maxSourceFiles={max_files}"
        )
        return matches[:max_files]
    return matches


def _add_repository_packages(
    root: Path,
    candidates: list[str],
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    manifests: list[tuple[Path, str, str]] = []
    for package_path in sorted(root.rglob("package.json")):
        relative = package_path.relative_to(root).as_posix()
        if _matches(relative, DEFAULT_EXCLUDE):
            continue
        package = read_json(package_path, {}) or {}
        name = package.get("name") if isinstance(package, dict) else None
        if isinstance(name, str) and name:
            manifests.append((package_path.parent, "npm", name))
    for pyproject_path in sorted(root.rglob("pyproject.toml")):
        relative = pyproject_path.relative_to(root).as_posix()
        if _matches(relative, DEFAULT_EXCLUDE):
            continue
        try:
            payload = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        name = payload.get("project", {}).get("name")
        if isinstance(name, str) and name:
            manifests.append((pyproject_path.parent, "python", name))
    for package_root, ecosystem, name in manifests:
        package_id = _node_id("package", f"{ecosystem}:{name}")
        nodes.setdefault(package_id, {
            "id": package_id,
            "type": "package",
            "label": name,
            "ecosystem": ecosystem,
            "external": False,
            "manifest": package_root.relative_to(root).as_posix() or ".",
        })
        for relative in candidates:
            path = root / relative
            if package_root == root or package_root in path.parents:
                source_id = _node_id(_path_node_type(relative), relative)
                _edge(edges, source_id, package_id, "belongs-to-package", relative)


def _add_import_edges(
    root: Path,
    path_nodes: dict[str, str],
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> None:
    python_modules = _python_modules(path_nodes)
    for relative, source_id in sorted(path_nodes.items()):
        path = root / relative
        suffix = path.suffix.lower()
        if suffix == ".py":
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=relative)
            except (OSError, UnicodeDecodeError, SyntaxError) as error:
                errors.append(f"Unable to parse Python architecture source {relative}: {error}")
                continue
            for target, line in _python_imports(relative, tree, python_modules):
                if target in path_nodes:
                    _edge(edges, source_id, path_nodes[target], "imports", relative, line)
                else:
                    package = target.split(".", 1)[0]
                    package_id = _external_package(nodes, "python", package)
                    _edge(edges, source_id, package_id, "imports", relative, line)
        elif suffix in JS_SUFFIXES:
            try:
                payload = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as error:
                warnings.append(f"Unable to inspect JavaScript architecture source {relative}: {error}")
                continue
            for match in JS_IMPORT_RE.finditer(payload):
                specifier = match.group(1)
                line = payload.count("\n", 0, match.start()) + 1
                target = _resolve_js_import(relative, specifier, path_nodes)
                if target:
                    _edge(edges, source_id, path_nodes[target], "imports", relative, line)
                elif not specifier.startswith((".", "/")):
                    package = _npm_package_name(specifier)
                    package_id = _external_package(nodes, "npm", package)
                    _edge(edges, source_id, package_id, "imports", relative, line)


def _add_api_nodes(
    root: Path,
    path_nodes: dict[str, str],
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
    warnings: list[str],
) -> None:
    route_ids: dict[str, list[str]] = {}
    for relative, source_id in sorted(path_nodes.items()):
        path = root / relative
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        try:
            payload = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            warnings.append(f"Unable to inspect API source {relative}: {error}")
            continue
        endpoints: list[tuple[str, str, int]] = []
        next_path = _next_route_path(relative)
        if next_path:
            for method in HTTP_METHODS:
                match = re.search(rf"\b(?:export\s+)?(?:async\s+)?function\s+{method}\b|\bexport\s+const\s+{method}\b", payload)
                if match:
                    endpoints.append((method, next_path, payload.count("\n", 0, match.start()) + 1))
        endpoint_patterns = []
        if path.suffix.lower() == ".py":
            endpoint_patterns.append(DECORATOR_API_RE)
        elif path.suffix.lower() in JS_SUFFIXES:
            endpoint_patterns.append(EXPRESS_API_RE)
        for regex in endpoint_patterns:
            for match in regex.finditer(payload):
                endpoints.append((match.group(1).upper(), match.group(2), payload.count("\n", 0, match.start()) + 1))
        for method, endpoint, line in sorted(set(endpoints)):
            api_id = _node_id("api", f"{method}:{endpoint}")
            nodes.setdefault(api_id, {
                "id": api_id,
                "type": "api",
                "label": f"{method} {endpoint}",
                "method": method,
                "route": endpoint,
            })
            route_ids.setdefault(endpoint, []).append(api_id)
            _edge(edges, source_id, api_id, "exposes-api", relative, line)

    for relative, source_id in sorted(path_nodes.items()):
        path = root / relative
        if path.suffix.lower() not in JS_SUFFIXES:
            continue
        try:
            payload = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for match in JS_API_CALL_RE.finditer(payload):
            endpoint = match.group(1).split("?", 1)[0]
            line = payload.count("\n", 0, match.start()) + 1
            api_ids = route_ids.get(endpoint)
            if not api_ids:
                api_id = _node_id("api", f"CALL:{endpoint}")
                nodes.setdefault(api_id, {
                    "id": api_id,
                    "type": "api",
                    "label": endpoint,
                    "method": "UNKNOWN",
                    "route": endpoint,
                    "external": not endpoint.startswith("/"),
                })
                api_ids = [api_id]
            for api_id in api_ids:
                _edge(edges, source_id, api_id, "calls-api", relative, line)


def _add_schema_usage_edges(
    root: Path,
    path_nodes: dict[str, str],
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
) -> None:
    schemas: list[tuple[str, str]] = []
    for relative, node_id in path_nodes.items():
        if _path_node_type(relative) == "schema":
            schemas.append((relative, node_id))
    for relative, source_id in sorted(path_nodes.items()):
        if source_id in {node_id for _, node_id in schemas}:
            continue
        path = root / relative
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        try:
            payload = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        for schema_path, schema_id in schemas:
            if schema_path in payload or Path(schema_path).name in payload:
                _edge(edges, source_id, schema_id, "uses-schema", relative)


def _add_intent_nodes(
    root: Path,
    manifest: dict[str, Any],
    config: dict[str, Any],
    path_nodes: dict[str, str],
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
    errors: list[str],
) -> None:
    intent = manifest.get("spec", {}).get("planes", {}).get("intent", {})
    if not intent.get("enabled"):
        return
    try:
        index_path = ensure_within(root, intent["index"])
    except (KeyError, ValueError) as error:
        errors.append(f"Invalid intent index binding for architecture graph: {error}")
        return
    index = read_json(index_path, {}) or {}
    journeys = {
        item.get("id"): item
        for item in index.get("journeys", [])
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    for journey_id, journey in sorted(journeys.items()):
        node_id = _node_id("journey", journey_id)
        nodes[node_id] = {
            "id": node_id,
            "type": "journey",
            "label": journey_id,
            "owner": journey.get("owner"),
            "status": journey.get("status"),
        }
        for test_path in journey.get("tests", []):
            target_id = path_nodes.get(test_path)
            if target_id:
                _edge(edges, node_id, target_id, "verified-by", intent["index"])
            else:
                errors.append(f"Journey {journey_id} test is outside the architecture graph: {test_path}")
    for binding in config.get("journeyBindings", []):
        journey_id = binding.get("journeyId") if isinstance(binding, dict) else None
        source_id = _node_id("journey", str(journey_id))
        if journey_id not in journeys:
            errors.append(f"Architecture graph journey binding references unknown journey: {journey_id}")
            continue
        for pattern in binding.get("paths", []):
            matched = False
            for relative, target_id in path_nodes.items():
                if _matches(relative, [pattern]):
                    _edge(edges, source_id, target_id, "implemented-by", "devctl.yaml")
                    matched = True
            if not matched:
                errors.append(f"Architecture graph journey binding matched no files: {journey_id} -> {pattern}")


def _add_ownership_nodes(
    root: Path,
    config: dict[str, Any],
    path_nodes: dict[str, str],
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
    errors: list[str],
) -> None:
    rules: list[dict[str, Any]] = []
    for relative in config.get("codeowners", [".github/CODEOWNERS", "CODEOWNERS"]):
        target = ensure_within(root, relative)
        if not target.is_file():
            continue
        for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            parts = stripped.split()
            if len(parts) < 2:
                errors.append(f"Invalid CODEOWNERS entry at {relative}:{line_number}")
                continue
            rules.append({
                "id": f"codeowners-{line_number}",
                "paths": [_codeowners_pattern(parts[0])],
                "owners": parts[1:],
                "source": f"{relative}:{line_number}",
            })
    rules.extend(config.get("ownershipRules", []))
    assignments: dict[str, tuple[list[str], str]] = {}
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        paths = rule.get("paths", [])
        owners = rule.get("owners", [])
        if not paths or not owners:
            errors.append(f"Architecture ownership rule is incomplete: {rule.get('id', '<unknown>')}")
            continue
        for relative in path_nodes:
            if _matches(relative, paths):
                assignments[relative] = (owners, str(rule.get("source", rule.get("id", "devctl.yaml"))))
    for relative, (owners, source) in sorted(assignments.items()):
        for owner in sorted(set(owners)):
            owner_id = _node_id("owner", owner)
            nodes.setdefault(owner_id, {
                "id": owner_id,
                "type": "owner",
                "label": owner,
            })
            _edge(edges, path_nodes[relative], owner_id, "owned-by", source)


def _add_security_nodes(
    config: dict[str, Any],
    path_nodes: dict[str, str],
    nodes: dict[str, dict[str, Any]],
    edges: dict[tuple[str, str, str], dict[str, Any]],
    errors: list[str],
) -> None:
    for rule in config.get("securityRules", []):
        if not isinstance(rule, dict):
            continue
        identifier = rule.get("id")
        paths = rule.get("paths", [])
        if not isinstance(identifier, str) or not identifier or not paths:
            errors.append("Architecture security rule requires id and paths")
            continue
        node_id = _node_id("security-boundary", identifier)
        nodes[node_id] = {
            "id": node_id,
            "type": "security-boundary",
            "label": identifier,
            "classification": rule.get("classification", "protected"),
            "authority": rule.get("authority", "repository owner"),
            "checks": sorted(set(rule.get("checks", []))),
        }
        matched = False
        for relative, source_id in path_nodes.items():
            if _matches(relative, paths):
                _edge(edges, source_id, node_id, "governed-by", "devctl.yaml")
                matched = True
        if not matched:
            errors.append(f"Architecture security rule matched no files: {identifier}")


def _python_modules(path_nodes: dict[str, str]) -> dict[str, str]:
    modules: dict[str, str] = {}
    for relative in path_nodes:
        if not relative.endswith(".py"):
            continue
        parts = Path(relative).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        if parts:
            modules[".".join(parts)] = relative
    return modules


def _python_imports(
    relative: str,
    tree: ast.AST,
    modules: dict[str, str],
) -> list[tuple[str, int]]:
    imports: list[tuple[str, int]] = []
    current = list(Path(relative).with_suffix("").parts[:-1])
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                keep = max(0, len(current) - node.level + 1)
                prefix = current[:keep]
                module = ".".join(prefix + ([node.module] if node.module else []))
            else:
                module = node.module or ""
            names = [module] if module else []
        for name in names:
            target = _resolve_python_module(name, modules)
            imports.append((target or name, getattr(node, "lineno", 1)))
    return imports


def _resolve_python_module(name: str, modules: dict[str, str]) -> str | None:
    candidate = name
    while candidate:
        if candidate in modules:
            return modules[candidate]
        candidate = candidate.rpartition(".")[0]
    return None


def _resolve_js_import(relative: str, specifier: str, path_nodes: dict[str, str]) -> str | None:
    if not specifier.startswith("."):
        return None
    base = (Path(relative).parent / specifier).as_posix()
    candidates = [base]
    if not Path(base).suffix:
        candidates.extend(base + suffix for suffix in JS_SUFFIXES)
        candidates.extend(f"{base}/index{suffix}" for suffix in JS_SUFFIXES)
    return next((candidate for candidate in candidates if candidate in path_nodes), None)


def _next_route_path(relative: str) -> str | None:
    match = re.match(r"^(?:src/)?app/(.+)/route\.(?:ts|tsx|js|jsx|mjs|cjs)$", relative)
    if not match:
        return None
    parts = [part for part in match.group(1).split("/") if not (part.startswith("(") and part.endswith(")"))]
    return "/" + "/".join(parts)


def _graph_config(manifest: dict[str, Any]) -> dict[str, Any]:
    return (
        manifest.get("spec", {})
        .get("planes", {})
        .get("architecture", {})
        .get("impactGraph", {"enabled": False})
    )


def _path_node_type(relative: str) -> str:
    suffix = Path(relative).suffix.lower()
    if relative.startswith("tests/") or "/tests/" in relative:
        return "test"
    if suffix in SCHEMA_SUFFIXES or relative.endswith(".schema.json") or "/schemas/" in relative:
        return "schema"
    return "file"


def _language(suffix: str) -> str:
    return {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".mjs": "javascript",
        ".cjs": "javascript",
    }[suffix]


def _external_package(nodes: dict[str, dict[str, Any]], ecosystem: str, name: str) -> str:
    node_id = _node_id("package", f"{ecosystem}:{name}")
    nodes.setdefault(node_id, {
        "id": node_id,
        "type": "package",
        "label": name,
        "ecosystem": ecosystem,
        "external": True,
    })
    return node_id


def _npm_package_name(specifier: str) -> str:
    parts = specifier.split("/")
    return "/".join(parts[:2]) if specifier.startswith("@") else parts[0]


def _edge(
    edges: dict[tuple[str, str, str], dict[str, Any]],
    source: str,
    target: str,
    edge_type: str,
    evidence_path: str,
    line: int | None = None,
) -> None:
    key = (source, edge_type, target)
    evidence: dict[str, Any] = {"path": evidence_path}
    if line is not None:
        evidence["line"] = line
    edges.setdefault(key, {
        "source": source,
        "target": target,
        "type": edge_type,
        "evidence": evidence,
    })


def _node_id(node_type: str, value: str) -> str:
    return f"{node_type}:{value.replace(chr(92), '/')}"


def _context_records(node_ids: Iterable[str], nodes: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    return [nodes[node_id] for node_id in sorted(node_ids)]


def _matches(path: str, patterns: Iterable[str]) -> bool:
    normalized = path.replace("\\", "/").lstrip("./")
    for pattern in patterns:
        normalized_pattern = str(pattern).replace("\\", "/").lstrip("./")
        variants = {normalized_pattern}
        reduced = normalized_pattern
        while "/**/" in reduced:
            reduced = reduced.replace("/**/", "/", 1)
            variants.add(reduced)
        if normalized_pattern.startswith("**/"):
            variants.add(normalized_pattern[3:])
        for variant in variants:
            if fnmatch.fnmatchcase(normalized, variant) or Path(normalized).match(variant):
                return True
            if variant.endswith("/**"):
                prefix = variant[:-3].rstrip("/")
                if normalized == prefix or normalized.startswith(prefix + "/"):
                    return True
    return False


def _codeowners_pattern(pattern: str) -> str:
    normalized = pattern.lstrip("/")
    if normalized.endswith("/"):
        return normalized + "**"
    if "/" not in normalized:
        return f"**/{normalized}"
    return normalized


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _empty_graph(root: Path, status: str, errors: list[str]) -> dict[str, Any]:
    return {
        "schemaVersion": GRAPH_SCHEMA_VERSION,
        "status": status,
        "root": str(root),
        "bounded": True,
        "nodeCount": 0,
        "edgeCount": 0,
        "nodes": [],
        "edges": [],
        "truncated": False,
        "errors": errors,
        "warnings": [],
    }
