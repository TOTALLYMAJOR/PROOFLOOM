from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from .governance import governance_design_preflight
from .storage import atomic_write_json, ensure_within, sha256_file


PROPOSAL_KIND = "proofloom/backlog-proposal"
PROPOSAL_STATUS = "REVIEW_REQUIRED"
DEFAULT_OUTPUT_PATH = "artifacts/design/backlog-proposals/proposed-backlog.json"
MAX_AUTHORITY_SOURCES = 30
AUTHORITY_EXTENSIONS = {".md", ".json", ".yaml", ".yml", ".toml"}
EXCLUDED_SOURCE_PREFIXES = (
    ".dev/governance/",
    ".design/baselines/",
    ".design/memory/schemas/",
    "artifacts/",
    "adapters/",
    "design_intelligence/data/schemas/",
    "node_modules/",
    "skills/",
    "templates/",
    "tests/fixtures/",
)
TASK_ID_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")
UNSAFE_COMMAND_PATTERN = re.compile(r"(?:&&|\|\||[;&|`<>]|[\r\n]|\$\()")
AUTHORITY_NAME_PATTERN = re.compile(
    r"(?:^|/)(?:agents|claude|readme|backlog|roadmap|project[-_ ]?state|vision|requirements?|"
    r"journeys?|intent[-_ ]?index|standards[-_ ]?profile|model[-_ ]?routing|architecture|adr|"
    r"decisions?|design|security|release|todo|package|pyproject|devctl)",
    re.IGNORECASE,
)


def assemble_backlog_brief(
    repository_root: str | Path,
    objective: str,
    *,
    surface: str | None = None,
) -> dict[str, Any]:
    root = _repository_root(repository_root)
    objective = _required_text(objective, "objective", maximum=500)
    preflight = governance_design_preflight(root)
    sources = _authority_sources(root)
    repository = {
        "root": str(root),
        "name": root.name,
        "branch": _git(root, "branch", "--show-current") or "detached",
        "commit": _git(root, "rev-parse", "HEAD") or "unavailable",
        "dirty": bool(_git(root, "status", "--porcelain")),
        "governanceGate": preflight.get("designGate", {}).get("status")
        or preflight.get("status", "UNKNOWN"),
    }
    schema = proposal_schema()
    guardrails = [
        "Repository authorities outrank this brief and any generated proposal.",
        "Inspect every listed source before drafting; report gaps instead of inventing product truth.",
        "Return proposed work only. Do not edit files, execute tasks, or claim completion.",
        "Do not create a second canonical backlog. This artifact remains REVIEW_REQUIRED until a human adopts it.",
        "Make dependencies acyclic, ownership non-overlapping, and validation commands argv-safe.",
        "AgentFlow may plan or execute only after a reviewed proposal is adopted through repository governance.",
    ]
    instruction = _build_ai_instruction(
        repository=repository,
        objective=objective,
        surface=surface,
        sources=sources,
        schema=schema,
        guardrails=guardrails,
    )
    return {
        "schemaVersion": 1,
        "kind": "proofloom/backlog-assembly-brief",
        "status": "AI_BRIEF_READY",
        "objective": objective,
        "surface": surface,
        "repository": repository,
        "authoritySources": sources,
        "guardrails": guardrails,
        "outputSchema": schema,
        "aiInstruction": instruction,
        "nextAction": "Give the instruction to a repository-capable AI, then paste its single JSON response back for validation.",
        "proofBoundary": (
            "This brief binds source paths and generation rules. It does not prove that an AI inspected them, "
            "make the proposal canonical, or authorize execution."
        ),
    }


def validate_backlog_proposal(
    repository_root: str | Path,
    proposal_input: str | dict[str, Any],
    *,
    expected_objective: str | None = None,
) -> dict[str, Any]:
    root = _repository_root(repository_root)
    proposal, parse_error = _parse_proposal(proposal_input)
    if parse_error:
        return _validation_report(None, [parse_error], [])

    errors: list[str] = []
    warnings: list[str] = []
    assert proposal is not None
    if proposal.get("schemaVersion") != 1:
        errors.append("schemaVersion must equal 1")
    if proposal.get("kind") != PROPOSAL_KIND:
        errors.append(f"kind must equal {PROPOSAL_KIND}")
    if proposal.get("proposalStatus") != PROPOSAL_STATUS:
        errors.append(f"proposalStatus must equal {PROPOSAL_STATUS}")
    _validate_string(proposal.get("objective"), "objective", errors)
    if (
        expected_objective is not None
        and _normalized_text(proposal.get("objective")) != _normalized_text(expected_objective)
    ):
        errors.append("objective must match the repository-bound assembly brief")

    coverage = proposal.get("coverage")
    if not isinstance(coverage, dict):
        errors.append("coverage must be an object")
    else:
        _validate_sources(root, coverage.get("sourcesReviewed"), errors)
        _validate_string_array(coverage.get("journeys"), "coverage.journeys", errors, nonempty=True)
        _validate_string_array(coverage.get("capabilities"), "coverage.capabilities", errors, nonempty=True)
        _validate_string_array(coverage.get("exclusions"), "coverage.exclusions", errors, nonempty=False)
        _validate_string_array(
            coverage.get("unresolvedQuestions"),
            "coverage.unresolvedQuestions",
            errors,
            nonempty=False,
        )
        _validate_string(coverage.get("completionBoundary"), "coverage.completionBoundary", errors)

    tasks = proposal.get("tasks")
    task_ids: set[str] = set()
    dependency_map: dict[str, list[str]] = {}
    ownership: list[tuple[str, str]] = []
    if not isinstance(tasks, list) or not tasks:
        errors.append("tasks must be a non-empty array")
        tasks = []
    for index, task in enumerate(tasks):
        prefix = f"tasks[{index}]"
        if not isinstance(task, dict):
            errors.append(f"{prefix} must be an object")
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not TASK_ID_PATTERN.fullmatch(task_id):
            errors.append(f"{prefix}.id must be an uppercase, hyphenated identifier such as MC-001")
            task_id = f"INVALID-{index}"
        elif task_id in task_ids:
            errors.append(f"{prefix}.id duplicates {task_id}")
        task_ids.add(task_id)
        _validate_string(task.get("title"), f"{prefix}.title", errors)
        _validate_string(task.get("description"), f"{prefix}.description", errors)
        if task.get("status") != "PROPOSED":
            errors.append(f"{prefix}.status must equal PROPOSED")
        depends_on = task.get("dependsOn")
        if not isinstance(depends_on, list) or not all(isinstance(item, str) and item for item in depends_on):
            errors.append(f"{prefix}.dependsOn must be an array of task IDs")
            depends_on = []
        dependency_map[task_id] = list(depends_on)
        task_ownership = task.get("ownership")
        _validate_string_array(task_ownership, f"{prefix}.ownership", errors, nonempty=True)
        if isinstance(task_ownership, list):
            for path in task_ownership:
                if isinstance(path, str) and path:
                    path_error = _relative_path_error(path)
                    if path_error:
                        errors.append(f"{prefix}.ownership path {path!r} {path_error}")
                    else:
                        ownership.append((task_id, path))
        _validate_string_array(
            task.get("acceptanceCriteria"),
            f"{prefix}.acceptanceCriteria",
            errors,
            nonempty=True,
        )
        validation = task.get("validation")
        _validate_string_array(validation, f"{prefix}.validation", errors, nonempty=True)
        if isinstance(validation, list):
            for command in validation:
                if isinstance(command, str) and UNSAFE_COMMAND_PATTERN.search(command):
                    errors.append(f"{prefix}.validation contains shell control syntax: {command!r}")
        _validate_string_array(
            task.get("evidenceRequired"),
            f"{prefix}.evidenceRequired",
            errors,
            nonempty=True,
        )

    for task_id, dependencies in dependency_map.items():
        for dependency in dependencies:
            if dependency not in task_ids:
                errors.append(f"task {task_id} depends on unknown task {dependency}")
            if dependency == task_id:
                errors.append(f"task {task_id} cannot depend on itself")
    cycle = _find_cycle(dependency_map)
    if cycle:
        errors.append(f"dependency cycle detected: {' -> '.join(cycle)}")
    _validate_ownership_overlap(ownership, errors)

    if not errors and not coverage.get("unresolvedQuestions"):
        warnings.append("coverage.unresolvedQuestions is empty; confirm that no product or authority decisions remain")
    return _validation_report(proposal, errors, warnings)


def save_backlog_proposal(
    repository_root: str | Path,
    proposal_input: str | dict[str, Any],
    output_path: str | Path = DEFAULT_OUTPUT_PATH,
    *,
    expected_objective: str | None = None,
) -> dict[str, Any]:
    root = _repository_root(repository_root)
    report = validate_backlog_proposal(root, proposal_input, expected_objective=expected_objective)
    if report["status"] != "VALID":
        raise ValueError("Backlog proposal failed validation and was not saved")
    destination = ensure_within(root, output_path)
    if destination == root:
        raise ValueError("Output path must name a JSON file inside the repository")
    if destination.suffix.lower() != ".json":
        raise ValueError("Output path must end in .json")
    if destination.exists():
        raise ValueError(f"Refusing to overwrite existing proposal: {destination.relative_to(root)}")
    proposal, _ = _parse_proposal(proposal_input)
    assert proposal is not None
    atomic_write_json(destination, proposal)
    return {
        "status": "SAVED_FOR_REVIEW",
        "path": destination.relative_to(root).as_posix(),
        "proposalSha256": sha256_file(destination),
        "taskCount": len(proposal["tasks"]),
        "canonical": False,
        "executionAuthorized": False,
        "nextAction": "Review the saved proposal and explicitly adopt it through the repository's canonical backlog process.",
        "proofBoundary": "Saving creates a non-canonical proposal only; it does not approve, commit, schedule, or execute work.",
    }


def proposal_schema() -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "kind": PROPOSAL_KIND,
        "proposalStatus": PROPOSAL_STATUS,
        "objective": "string",
        "coverage": {
            "sourcesReviewed": [{"path": "relative/path", "role": "authority role", "finding": "what it establishes"}],
            "journeys": ["journey or stage covered"],
            "capabilities": ["capability covered"],
            "exclusions": ["explicit exclusion"],
            "unresolvedQuestions": ["decision still needed"],
            "completionBoundary": "what completion of this proposed portfolio would and would not prove",
        },
        "tasks": [
            {
                "id": "PROJECT-001",
                "title": "string",
                "description": "string",
                "status": "PROPOSED",
                "dependsOn": [],
                "ownership": ["repository/relative/path"],
                "acceptanceCriteria": ["observable criterion"],
                "validation": ["argv-safe validation command without shell control syntax"],
                "evidenceRequired": ["artifact or observation required before terminal status"],
            }
        ],
    }


def _build_ai_instruction(
    *,
    repository: dict[str, Any],
    objective: str,
    surface: str | None,
    sources: list[dict[str, str]],
    schema: dict[str, Any],
    guardrails: list[str],
) -> str:
    source_lines = "\n".join(
        f"- {item['path']} [{item['role']}] sha256:{item['sha256']}" for item in sources
    ) or "- No authority-like tracked sources were discovered; report this as an unresolved question."
    rules = "\n".join(f"{index}. {rule}" for index, rule in enumerate(guardrails, start=1))
    surface_line = f"\nSurface or program focus: {surface}" if surface else ""
    return (
        "You are assembling a complete proposed backlog from repository evidence.\n\n"
        f"Repository: {repository['root']}\n"
        f"Bound revision: {repository['commit']} on {repository['branch']}\n"
        f"Objective: {objective}{surface_line}\n\n"
        "Read and reconcile these sources before drafting:\n"
        f"{source_lines}\n\n"
        "Rules:\n"
        f"{rules}\n\n"
        "Cover the end-to-end user journeys, product capabilities, implementation work, negative and recovery states, "
        "accessibility, security, data or migration needs, tests, release controls, and evidence needed by this objective. "
        "Preserve existing authorities and record contradictions under unresolvedQuestions. Every task must have exclusive "
        "repository-relative ownership, observable acceptance criteria, dependency IDs, argv-safe validation commands, "
        "and terminal evidence requirements.\n\n"
        "Return exactly one JSON object, with no Markdown fence or commentary, matching this shape:\n"
        f"{json.dumps(schema, indent=2)}"
    )


def _authority_sources(root: Path) -> list[dict[str, str]]:
    tracked = _git_lines(root, "ls-files")
    if not tracked:
        tracked = [path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file()]
    candidates = [
        path
        for path in tracked
        if AUTHORITY_NAME_PATTERN.search(path)
        and PurePosixPath(path).suffix.lower() in AUTHORITY_EXTENSIONS
        and not path.startswith(EXCLUDED_SOURCE_PREFIXES)
        and not PurePosixPath(path).name.lower().startswith("release-report-")
    ]
    candidates.sort(key=lambda path: (_source_priority(path), path.count("/"), path.lower()))
    result: list[dict[str, str]] = []
    for relative in candidates[:MAX_AUTHORITY_SOURCES]:
        path = root / relative
        if not path.is_file():
            continue
        result.append({"path": relative, "role": _source_role(relative), "sha256": sha256_file(path)})
    return result


def _source_priority(path: str) -> int:
    name = PurePosixPath(path).name.lower()
    if name in {"agents.md", "claude.md"}:
        return 0
    if "vision" in name or "requirement" in name or "journey" in name:
        return 1
    if name in {"intent-index.json", "standards-profile.json", "model-routing.json"}:
        return 1
    if "architecture" in name or name.startswith("adr") or "decision" in path.lower():
        return 2
    if "backlog" in name or "roadmap" in name or "project_state" in name:
        return 3
    if name in {"readme.md", "devctl.yaml", "package.json", "pyproject.toml"}:
        return 4
    return 5


def _source_role(path: str) -> str:
    lowered = path.lower()
    for role, signals in (
        ("instructions", ("agents.md", "claude.md")),
        ("journey", ("journey", "persona", "actor")),
        ("requirements", ("requirement", "vision", "prd")),
        ("architecture", ("architecture", "adr", "decision")),
        ("backlog", ("backlog", "roadmap", "todo", "project_state")),
        ("design", ("design",)),
        ("delivery", ("package.json", "pyproject.toml", "release", "devctl")),
    ):
        if any(signal in lowered for signal in signals):
            return role
    return "repository context"


def _validate_sources(root: Path, value: Any, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append("coverage.sourcesReviewed must be a non-empty array")
        return
    for index, item in enumerate(value):
        prefix = f"coverage.sourcesReviewed[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        for key in ("path", "role", "finding"):
            _validate_string(item.get(key), f"{prefix}.{key}", errors)
        path = item.get("path")
        if isinstance(path, str) and path:
            path_error = _relative_path_error(path)
            if path_error:
                errors.append(f"{prefix}.path {path!r} {path_error}")
            elif not (root / path).is_file():
                errors.append(f"{prefix}.path does not exist in the repository: {path}")


def _validate_string(value: Any, label: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")


def _validate_string_array(value: Any, label: str, errors: list[str], *, nonempty: bool) -> None:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return
    if nonempty and not value:
        errors.append(f"{label} must not be empty")
    if not all(isinstance(item, str) and item.strip() for item in value):
        errors.append(f"{label} must contain only non-empty strings")


def _relative_path_error(value: str) -> str | None:
    candidate = PurePosixPath(value)
    if candidate.is_absolute():
        return "must be repository-relative"
    if not value.strip() or value.startswith("~") or candidate == PurePosixPath(".") or ".." in candidate.parts:
        return "must not be empty, home-relative, or escape the repository"
    return None


def _validate_ownership_overlap(ownership: list[tuple[str, str]], errors: list[str]) -> None:
    normalized = [(task, PurePosixPath(path).parts, path) for task, path in ownership]
    for index, (task_a, parts_a, path_a) in enumerate(normalized):
        for task_b, parts_b, path_b in normalized[index + 1 :]:
            if task_a == task_b:
                continue
            shorter = min(len(parts_a), len(parts_b))
            if parts_a[:shorter] == parts_b[:shorter]:
                errors.append(f"ownership overlaps between {task_a}:{path_a} and {task_b}:{path_b}")


def _find_cycle(graph: dict[str, list[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []

    def visit(node: str) -> list[str] | None:
        if node in visiting:
            start = stack.index(node)
            return stack[start:] + [node]
        if node in visited:
            return None
        visiting.add(node)
        stack.append(node)
        for dependency in graph.get(node, []):
            if dependency in graph:
                found = visit(dependency)
                if found:
                    return found
        stack.pop()
        visiting.remove(node)
        visited.add(node)
        return None

    for node in graph:
        found = visit(node)
        if found:
            return found
    return None


def _validation_report(
    proposal: dict[str, Any] | None,
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    encoded = json.dumps(proposal, sort_keys=True, separators=(",", ":")) if proposal is not None else ""
    return {
        "status": "INVALID" if errors else "VALID",
        "errors": errors,
        "warnings": warnings,
        "taskCount": len(proposal.get("tasks", [])) if proposal else 0,
        "proposalSha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest() if proposal is not None else None,
        "canonical": False,
        "executionAuthorized": False,
        "proofBoundary": "Validation proves contract shape and deterministic safety checks only, not product completeness.",
    }


def _parse_proposal(value: str | dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(value, dict):
        return value, None
    if not isinstance(value, str) or not value.strip():
        return None, "proposal must be a JSON object or a non-empty JSON string"
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        return None, f"proposal is not valid JSON: line {error.lineno}, column {error.colno}"
    if not isinstance(parsed, dict):
        return None, "proposal JSON must contain one object"
    return parsed, None


def _required_text(value: Any, label: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return " ".join(value.split())[:maximum]


def _normalized_text(value: Any) -> str:
    return " ".join(value.split()) if isinstance(value, str) else ""


def _repository_root(value: str | Path) -> Path:
    root = Path(value).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"Repository root does not exist: {root}")
    return root


def _git(root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _git_lines(root: Path, *args: str) -> list[str]:
    output = _git(root, *args)
    return [line for line in output.splitlines() if line]
