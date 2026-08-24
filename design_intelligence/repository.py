from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path

from .models import (
    CapabilityAuthority,
    CapabilitySignal,
    DesignMemoryAuthority,
    DuplicateAuthority,
    Presence,
    Recommendation,
    RepositoryMaturity,
    RepositorySnapshot,
    Severity,
)

IGNORED_DIR_NAMES = {
    ".git",
    ".next",
    ".turbo",
    ".vercel",
    ".cache",
    ".history",
    ".venv",
    "coverage",
    "dist",
    "build",
    "node_modules",
    "vendor",
    "__pycache__",
}

TEST_DATA_DIR_NAMES = {"fixtures", "__fixtures__", "snapshots", "__snapshots__"}

DIRECTORY_HINTS = [
    "docs",
    "design",
    "architecture",
    "product",
    "specs",
    "requirements",
    "roadmap",
    "tasks",
    "backlog",
    "app",
    "pages",
    "src",
    "components",
    "components2",
    "ui",
    "shared-ui",
    "design-system",
    "packages",
    "libs",
    "styles",
    ".storybook",
    "tests",
    "e2e",
    "cypress",
    ".github",
    ".agents",
    ".codex",
    ".claude",
    ".cursor",
    ".windsurf",
    ".husky",
    ".githooks",
]

EXPLICIT_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "README.mdx",
    "ARCHITECTURE.md",
    "DESIGN.md",
    "FRONTEND.md",
    "PRODUCT_SENSE.md",
    "QUALITY_SCORE.md",
    "SECURITY.md",
    "BACKLOG.md",
    "ROADMAP.md",
    "CONTRIBUTING.md",
    "RELATIONS.md",
    "package.json",
    "pyproject.toml",
    "tailwind.config.js",
    "tailwind.config.cjs",
    "tailwind.config.mjs",
    "tailwind.config.ts",
    "playwright.config.js",
    "playwright.config.ts",
    "cypress.config.js",
    "cypress.config.ts",
    "vitest.config.js",
    "vitest.config.ts",
    "jest.config.js",
    "jest.config.ts",
    "eslint.config.js",
    "eslint.config.mjs",
    ".storybook/main.ts",
    ".storybook/main.js",
    ".github/copilot-instructions.md",
    ".cursorrules",
    ".windsurfrules",
    ".pre-commit-config.yaml",
    "lefthook.yml",
    "lefthook.yaml",
]

TEXT_EXTENSIONS = {
    ".css",
    ".cjs",
    ".html",
    ".js",
    ".json",
    ".jsx",
    ".md",
    ".mdx",
    ".mjs",
    ".py",
    ".toml",
    ".ts",
    ".tsx",
    ".txt",
    ".yaml",
    ".yml",
}

DESIGN_KEYWORDS = (
    "a11y",
    "accessibility",
    "agent",
    "architecture",
    "backlog",
    "badge",
    "button",
    "card",
    "component",
    "decision",
    "debt",
    "design",
    "dialog",
    "drawer",
    "e2e",
    "form",
    "global",
    "header",
    "input",
    "instruction",
    "layout",
    "hook",
    "modal",
    "nav",
    "page",
    "playwright",
    "product",
    "roadmap",
    "story",
    "style",
    "tailwind",
    "theme",
    "token",
    "typography",
    "ui",
    "workflow",
)

DUPLICATE_CAPABILITIES = {
    "agent_governance",
    "architecture_overview",
    "design_language",
    "design_decisions",
    "backlog",
}

MAX_FILES = 260
MAX_BYTES = 192_000


def inspect_repository(root: str | Path) -> RepositorySnapshot:
    root_path = Path(root).resolve()
    candidate_files = select_candidate_files(root_path)
    contents = {path: _read_text(path) for path in candidate_files}
    package_info = _load_package_info(root_path / "package.json")
    dependencies = set(package_info.get("dependencies", {})) | set(
        package_info.get("devDependencies", {})
    )

    capability_authorities = _collect_capabilities(root_path, candidate_files, contents)
    if (root_path / ".design/memory/decisions.jsonl").is_file():
        capability_authorities.setdefault("design_decisions", []).append(".design/memory/decisions.jsonl")
    if (root_path / ".design/memory/debt.jsonl").is_file():
        capability_authorities.setdefault("design_debt", []).append(".design/memory/debt.jsonl")
    if "@playwright/test" in dependencies:
        capability_authorities.setdefault("testing_e2e", []).append("package.json")
        capability_authorities.setdefault("visual_validation", []).append("package.json")
    if "cypress" in dependencies:
        capability_authorities.setdefault("testing_e2e", []).append("package.json")
        capability_authorities.setdefault("visual_validation", []).append("package.json")
    if any(dep in dependencies for dep in ("eslint-plugin-jsx-a11y", "axe-core", "@axe-core/playwright")):
        capability_authorities.setdefault("accessibility_validation", []).append("package.json")
    capability_authorities = {
        key: sorted(set(values)) for key, values in capability_authorities.items()
    }
    frontend = _detect_frontend(dependencies, candidate_files)
    styling = _detect_styling(dependencies, candidate_files, contents)
    component_system = _detect_component_system(root_path, dependencies)
    design_tokens = _detect_design_tokens(contents, candidate_files)
    typography = _detect_typography(contents)
    design_documentation = _signal_for_capability(capability_authorities, "design_language")
    agent_governance = _signal_for_capability(capability_authorities, "agent_governance")
    playwright = _detect_test_tool(
        capability_authorities,
        "testing_e2e",
        "playwright",
        dependency_present="@playwright/test" in dependencies,
    )
    cypress = _detect_test_tool(
        capability_authorities,
        "testing_e2e",
        "cypress",
        dependency_present="cypress" in dependencies,
    )
    storybook = _signal_for_capability(capability_authorities, "storybook")
    accessibility_tooling = _detect_accessibility(capability_authorities, dependencies, contents)
    existing_design_skills = _detect_existing_design_skills(root_path)
    design_memory = _detect_design_memory(capability_authorities)
    capability_map = _build_capability_map(capability_authorities)
    semantic_duplicates = _detect_semantic_duplicates(capability_map, component_system)
    notes = _build_notes(semantic_duplicates, component_system, design_memory, existing_design_skills)
    maturity = _classify_maturity(
        frontend=frontend,
        styling=styling,
        component_system=component_system,
        design_tokens=design_tokens,
        design_documentation=design_documentation,
        agent_governance=agent_governance,
        playwright=playwright,
        storybook=storybook,
    )

    return RepositorySnapshot(
        root=str(root_path),
        scanned_paths=DIRECTORY_HINTS,
        ignored_patterns=sorted(IGNORED_DIR_NAMES),
        files_considered=[str(path.relative_to(root_path)) for path in candidate_files],
        frontend=frontend,
        styling=styling,
        component_system=component_system,
        repository_maturity=maturity,
        design_tokens=design_tokens,
        typography=typography,
        design_documentation=design_documentation,
        agent_governance=agent_governance,
        playwright=playwright,
        cypress=cypress,
        storybook=storybook,
        accessibility_tooling=accessibility_tooling,
        existing_design_skills=existing_design_skills,
        institutional_design_memory=design_memory,
        capability_map=capability_map,
        semantic_duplicates=semantic_duplicates,
        notes=notes,
    )


def select_candidate_files(root: Path) -> list[Path]:
    selected: list[Path] = []
    seen: set[Path] = set()

    for explicit in EXPLICIT_FILES:
        path = root / explicit
        if path.is_file():
            selected.append(path)
            seen.add(path)

    for directory_hint in DIRECTORY_HINTS:
        base = root / directory_hint
        if not base.exists():
            continue
        for current_root, dirnames, filenames in os.walk(base):
            current = Path(current_root)
            relative = current.relative_to(base)
            if len(relative.parts) > 4:
                dirnames[:] = []
                continue
            dirnames[:] = [name for name in dirnames if name not in IGNORED_DIR_NAMES]
            if base == root / "tests" and current == base:
                dirnames[:] = [name for name in dirnames if name not in TEST_DATA_DIR_NAMES]
            for filename in filenames:
                path = current / filename
                if path in seen or not _looks_relevant(path, base):
                    continue
                selected.append(path)
                seen.add(path)
                if len(selected) >= MAX_FILES:
                    return sorted(selected)
    return sorted(selected)


def _looks_relevant(path: Path, base: Path) -> bool:
    extensionless_hook = base.name in {".husky", ".githooks"} and not path.suffix
    if path.suffix.lower() not in TEXT_EXTENSIONS and not extensionless_hook:
        return False
    if path.stat().st_size > MAX_BYTES:
        return False
    try:
        relative = str(path.relative_to(base)).lower()
    except ValueError:
        relative = path.name.lower()
    if base.name in {
        "docs", "design", "architecture", "product", "specs", "requirements", "roadmap",
        ".agents", ".codex", ".claude", ".cursor", ".windsurf", ".husky", ".githooks",
    }:
        return True
    return any(keyword in relative for keyword in DESIGN_KEYWORDS)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_package_info(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _collect_capabilities(
    root: Path, candidate_files: list[Path], contents: dict[Path, str]
) -> dict[str, list[str]]:
    capabilities: dict[str, list[str]] = defaultdict(list)
    for path in candidate_files:
        relative = str(path.relative_to(root))
        lowered = relative.lower()
        normalized_lowered = lowered.replace("_", "-")
        text = contents[path].lower()
        name = path.name.lower()

        if path.name in {"AGENTS.md", "CLAUDE.md"}:
            capabilities["agent_governance"].append(relative)

        if (
            "copilot-instructions" in lowered
            or lowered.startswith((".agents/", ".codex/", ".claude/", ".cursor/", ".windsurf/"))
            or name in {".cursorrules", ".windsurfrules"}
        ):
            capabilities["custom_instructions"].append(relative)

        if (
            lowered.startswith((".husky/", ".githooks/"))
            or name in {".pre-commit-config.yaml", "lefthook.yml", "lefthook.yaml"}
        ):
            capabilities["hooks"].append(relative)

        if (
            "architecture" in lowered
            or path.name in {"ARCHITECTURE.md", "FRONTEND.md"}
            or lowered.startswith("docs/architecture")
        ):
            capabilities["architecture_overview"].append(relative)

        if any(token in lowered for token in ("adr", "decision", "rfc")) and "design-intelligence: derived-view" not in text:
            if "design" in lowered or "ui" in lowered:
                capabilities["design_decisions"].append(relative)
            else:
                capabilities["architecture_decisions"].append(relative)

        if any(token in normalized_lowered for token in ("design-system", "design-language")):
            if path.suffix.lower() in {".md", ".mdx"} or "tailwind.config" in name or path.suffix == ".css":
                capabilities["design_language"].append(relative)
        if "design-principles" in normalized_lowered and path.suffix.lower() in {".md", ".mdx"}:
            capabilities["design_principles"].append(relative)
        if "design-contract" in normalized_lowered and path.suffix.lower() in {".md", ".mdx"}:
            capabilities["design_contracts"].append(relative)

        if any(token in lowered for token in ("debt", "design-debt")) and "design-intelligence: derived-view" not in text:
            if "design" in lowered or "ui" in lowered:
                capabilities["design_debt"].append(relative)
            else:
                capabilities["technical_debt"].append(relative)

        if any(token in lowered for token in ("backlog", "tasks", "roadmap", "plans")):
            capabilities["backlog"].append(relative)

        if any(token in lowered for token in ("spec", "requirement", "product")) and path.suffix.lower() in {
            ".md",
            ".mdx",
        }:
            capabilities["specifications"].append(relative)

        if "playwright" in lowered or lowered.startswith("e2e/") or "/e2e/" in lowered:
            capabilities["testing_e2e"].append(relative)
            capabilities["visual_validation"].append(relative)

        if "cypress" in lowered:
            capabilities["testing_e2e"].append(relative)
            capabilities["visual_validation"].append(relative)

        if "storybook" in lowered or lowered.startswith(".storybook/"):
            capabilities["storybook"].append(relative)
            capabilities["visual_validation"].append(relative)

        if (
            "vitest" in lowered
            or "jest" in lowered
            or lowered.startswith("tests/unit")
            or "/__tests__/" in lowered
        ):
            capabilities["testing_unit"].append(relative)

        if "a11y" in lowered or "accessibility" in lowered or "aria-" in text or "axe" in text:
            capabilities["accessibility_validation"].append(relative)

        if lowered.startswith("skills/") and any(
            segment in lowered
            for segment in (
                "design-language",
                "ux-architect",
                "reference-intelligence",
                "visual-review",
                "design-linter",
            )
        ):
            capabilities["design_skills"].append(relative)

    for folder in (
        "components",
        "components/ui",
        "components2",
        "ui",
        "shared-ui",
        "design-system",
        "src/components",
    ):
        if (root / folder).exists():
            capabilities["component_directories"].append(folder)

    return {key: sorted(set(values)) for key, values in capabilities.items()}


def _detect_frontend(dependencies: set[str], candidate_files: list[Path]) -> str:
    if "next" in dependencies:
        return "Next.js"
    if "react" in dependencies:
        return "React"
    if "vue" in dependencies:
        return "Vue"
    if "svelte" in dependencies:
        return "Svelte"
    if any(path.suffix in {".tsx", ".jsx"} for path in candidate_files):
        return "React-family"
    return "Unknown"


def _detect_styling(
    dependencies: set[str], candidate_files: list[Path], contents: dict[Path, str]
) -> str:
    if "tailwindcss" in dependencies or any("tailwind.config" in path.name for path in candidate_files):
        return "Tailwind"
    if "styled-components" in dependencies:
        return "styled-components"
    if "@emotion/react" in dependencies:
        return "Emotion"
    if "sass" in dependencies:
        return "Sass"
    if any(path.name.endswith(".module.css") for path in candidate_files):
        return "CSS Modules"
    if any(path.suffix == ".css" and "var(" in text for path, text in contents.items()):
        return "CSS custom properties"
    if any(path.suffix == ".css" for path in candidate_files):
        return "CSS"
    return "Unknown"


def _detect_component_system(root: Path, dependencies: set[str]) -> str:
    independent_dirs = [
        folder
        for folder in ("components", "components2", "ui", "shared-ui", "design-system", "src/components")
        if (root / folder).exists()
    ]
    competing_alternatives = [
        folder
        for folder in independent_dirs
        if folder not in {"components", "src/components"}
    ]
    if (root / "components/ui").exists() and any(dep.startswith("@radix-ui/") for dep in dependencies):
        if competing_alternatives:
            return "shadcn + competing local primitives"
        return "shadcn + local primitives"
    if len(independent_dirs) >= 2:
        return "Competing local UI systems"
    if (root / "components").exists() or (root / "src/components").exists():
        return "Local components"
    return "Unknown"


def _detect_design_tokens(contents: dict[Path, str], candidate_files: list[Path]) -> CapabilitySignal:
    evidence: list[str] = []
    for path, text in contents.items():
        if "tailwind.config" in path.name and any(term in text for term in ("extend", "theme", "colors")):
            evidence.append(path.name)
        if path.suffix == ".css" and "--" in text and ("var(" in text or ":root" in text):
            evidence.append(path.name)
        if "token" in path.name.lower():
            evidence.append(path.name)
    return _signal_from_evidence(evidence, "Detected token-like configuration or CSS custom properties.")


def _detect_typography(contents: dict[Path, str]) -> CapabilitySignal:
    evidence: list[str] = []
    for path, text in contents.items():
        if any(token in text for token in ("fontFamily", "next/font", "@font-face", "font-family")):
            evidence.append(path.name)
    if len(evidence) == 1:
        return CapabilitySignal(
            status=Presence.PARTIAL,
            evidence=sorted(set(evidence)),
            note="One typography authority found; hierarchy may still be implicit.",
        )
    return _signal_from_evidence(evidence, "Detected explicit typography configuration.")


def _detect_test_tool(
    capability_authorities: dict[str, list[str]],
    capability: str,
    token: str,
    dependency_present: bool = False,
) -> CapabilitySignal:
    evidence = [
        path for path in capability_authorities.get(capability, []) if token in path.lower()
    ]
    if not evidence and dependency_present and "package.json" in capability_authorities.get(capability, []):
        evidence = ["package.json"]
    return _signal_from_evidence(evidence, f"Detected {token} evidence.")


def _detect_accessibility(
    capabilities: dict[str, list[str]], dependencies: set[str], contents: dict[Path, str]
) -> CapabilitySignal:
    evidence = list(capabilities.get("accessibility_validation", []))
    for dependency in ("eslint-plugin-jsx-a11y", "axe-core", "@axe-core/playwright"):
        if dependency in dependencies:
            evidence.append("package.json")
    if not evidence:
        return CapabilitySignal(status=Presence.NONE, evidence=[])
    status = Presence.PRESENT if "package.json" in evidence else Presence.PARTIAL
    return CapabilitySignal(status=status, evidence=sorted(set(evidence)))


def _detect_existing_design_skills(root: Path) -> CapabilitySignal:
    skills_root = root / "skills"
    evidence: list[str] = []
    if skills_root.exists():
        for child in skills_root.iterdir():
            if child.is_dir() and child.name in {
                "design-language",
                "ux-architect",
                "reference-intelligence",
                "visual-review",
                "design-linter",
            }:
                evidence.append(f"skills/{child.name}")
    return _signal_from_evidence(evidence, "Design Intelligence skills are already present.")


def _detect_design_memory(capabilities: dict[str, list[str]]) -> DesignMemoryAuthority:
    authority_paths = capabilities.get("design_decisions", []) or capabilities.get(
        "architecture_decisions", []
    )
    if authority_paths:
        return DesignMemoryAuthority(
            authority_paths=authority_paths,
            fallback_path="docs/design/decisions",
            strategy=Recommendation.INTEGRATE,
            note="Reuse the repository's existing decision history before adding a fallback store.",
        )
    return DesignMemoryAuthority(
        authority_paths=[],
        fallback_path="docs/design/decisions",
        strategy=Recommendation.ADD,
        note="No design-decision authority detected; a lightweight Git-friendly fallback is justified.",
    )


def _build_capability_map(capabilities: dict[str, list[str]]) -> dict[str, CapabilityAuthority]:
    map_items: dict[str, CapabilityAuthority] = {}
    tracked = {
        "agent_governance",
        "custom_instructions",
        "hooks",
        "architecture_overview",
        "architecture_decisions",
        "design_language",
        "design_principles",
        "design_contracts",
        "design_decisions",
        "design_debt",
        "technical_debt",
        "backlog",
        "specifications",
        "testing_unit",
        "testing_e2e",
        "visual_validation",
        "accessibility_validation",
        "design_skills",
        "storybook",
    }
    for capability in sorted(tracked):
        authorities = capabilities.get(capability, [])
        if not authorities:
            map_items[capability] = CapabilityAuthority(
                capability=capability,
                status=Presence.NONE,
                authorities=[],
                strategy=Recommendation.ADD,
                note="No authority detected.",
            )
            continue
        if capability in DUPLICATE_CAPABILITIES and len(authorities) > 1:
            strategy = Recommendation.MIGRATE
            status = Presence.PARTIAL
            note = "Multiple candidate authorities detected; converge before adding more."
        else:
            strategy = Recommendation.INTEGRATE
            status = Presence.PRESENT
            note = "Existing authority detected."
        map_items[capability] = CapabilityAuthority(
            capability=capability,
            status=status,
            authorities=authorities,
            strategy=strategy,
            note=note,
        )
    return map_items


def _detect_semantic_duplicates(
    capability_map: dict[str, CapabilityAuthority], component_system: str
) -> list[DuplicateAuthority]:
    duplicates: list[DuplicateAuthority] = []
    for capability, item in capability_map.items():
        if capability in DUPLICATE_CAPABILITIES and len(item.authorities) > 1:
            severity = Severity.P1 if capability in {"agent_governance", "design_language"} else Severity.P2
            duplicates.append(
                DuplicateAuthority(
                    capability=capability,
                    authorities=item.authorities,
                    severity=severity,
                    note="Capability appears to have more than one active authority.",
                )
            )
    if component_system == "Competing local UI systems":
        duplicates.append(
            DuplicateAuthority(
                capability="component_system",
                authorities=["components", "components2", "ui or shared-ui"],
                severity=Severity.P1,
                note="Competing UI system directories suggest progressive convergence is safer than adding another layer.",
            )
        )
    return duplicates


def _signal_for_capability(
    capability_map: dict[str, list[str]], capability: str
) -> CapabilitySignal:
    evidence = capability_map.get(capability, [])
    if not evidence:
        return CapabilitySignal(status=Presence.NONE, evidence=[])
    status = Presence.PARTIAL if len(evidence) > 1 else Presence.PRESENT
    note = "Multiple authorities detected." if len(evidence) > 1 else None
    return CapabilitySignal(status=status, evidence=evidence, note=note)


def _signal_from_evidence(evidence: list[str], note: str) -> CapabilitySignal:
    unique = sorted(set(evidence))
    if not unique:
        return CapabilitySignal(status=Presence.NONE, evidence=[])
    status = Presence.PRESENT if len(unique) >= 2 else Presence.PARTIAL
    return CapabilitySignal(status=status, evidence=unique, note=note)


def _build_notes(
    duplicates: list[DuplicateAuthority],
    component_system: str,
    design_memory: DesignMemoryAuthority,
    existing_design_skills: CapabilitySignal,
) -> list[str]:
    notes: list[str] = []
    for duplicate in duplicates:
        notes.append(f"Possible dual authority: {duplicate.capability}.")
    if component_system == "Competing local UI systems":
        notes.append("Bounded consolidation through adapters or facades is safer than a broad replacement.")
    if design_memory.authority_paths:
        notes.append("Institutional design memory already exists; reuse it instead of adding a second decision store.")
    if existing_design_skills.status == Presence.PRESENT:
        notes.append("Existing design skills should outrank package defaults when current.")
    return notes


def _classify_maturity(
    *,
    frontend: str,
    styling: str,
    component_system: str,
    design_tokens: CapabilitySignal,
    design_documentation: CapabilitySignal,
    agent_governance: CapabilitySignal,
    playwright: CapabilitySignal,
    storybook: CapabilitySignal,
) -> RepositoryMaturity:
    score = 0
    if frontend != "Unknown":
        score += 1
    if styling != "Unknown":
        score += 1
    if component_system != "Unknown":
        score += 1
    if design_tokens.status != Presence.NONE:
        score += 1
    if design_documentation.status != Presence.NONE:
        score += 1
    if agent_governance.status != Presence.NONE:
        score += 1
    if playwright.status != Presence.NONE:
        score += 1
    if storybook.status != Presence.NONE:
        score += 1

    if score >= 6:
        return RepositoryMaturity.ESTABLISHED
    if score >= 3:
        return RepositoryMaturity.PARTIAL
    return RepositoryMaturity.GREENFIELD


def render_snapshot_text(snapshot: RepositorySnapshot) -> str:
    lines = [
        "DESIGN REPOSITORY SNAPSHOT",
        "",
        f"Root: {snapshot.root}",
        f"Repository maturity: {snapshot.repository_maturity.value}",
        f"Frontend: {snapshot.frontend}",
        f"Styling: {snapshot.styling}",
        f"Component system: {snapshot.component_system}",
        f"Design tokens: {snapshot.design_tokens.status.value}",
        f"Typography: {snapshot.typography.status.value}",
        f"Design documentation: {snapshot.design_documentation.status.value}",
        f"Agent governance: {snapshot.agent_governance.status.value}",
        f"Playwright: {snapshot.playwright.status.value}",
        f"Cypress: {snapshot.cypress.status.value}",
        f"Storybook: {snapshot.storybook.status.value}",
        f"Accessibility tooling: {snapshot.accessibility_tooling.status.value}",
        f"Design memory authority: {', '.join(snapshot.institutional_design_memory.authority_paths) or 'NONE'}",
        "",
        "Semantic duplicates:",
    ]
    if snapshot.semantic_duplicates:
        for duplicate in snapshot.semantic_duplicates:
            lines.append(
                f"- {duplicate.capability}: {', '.join(duplicate.authorities)} ({duplicate.severity.value})"
            )
    else:
        lines.append("- none detected")
    lines.extend(["", "Files considered:"])
    lines.extend(f"- {path}" for path in snapshot.files_considered)
    if snapshot.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {note}" for note in snapshot.notes)
    return "\n".join(lines)
