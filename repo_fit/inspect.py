from __future__ import annotations

import argparse
import json
import os
from collections import defaultdict
from pathlib import Path

from .models import CapabilitySignal, Presence, RepositoryMaturity, RepositorySnapshot

IGNORED_DIR_NAMES = {
    ".git",
    ".next",
    ".turbo",
    ".vercel",
    ".cache",
    "node_modules",
    "dist",
    "build",
    "coverage",
    "vendor",
}

DIRECTORY_HINTS = [
    "docs",
    "design",
    "architecture",
    "product",
    "app",
    "pages",
    "src",
    "components",
    "components/ui",
    "styles",
    ".github/workflows",
    "tests",
]

EXPLICIT_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "README.mdx",
    "package.json",
    "pyproject.toml",
    "tailwind.config.js",
    "tailwind.config.cjs",
    "tailwind.config.mjs",
    "tailwind.config.ts",
    "playwright.config.js",
    "playwright.config.ts",
    "vitest.config.js",
    "vitest.config.ts",
    "jest.config.js",
    "jest.config.ts",
    "eslint.config.js",
    "eslint.config.mjs",
]

TEXT_EXTENSIONS = {
    ".css",
    ".cjs",
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
    ".yaml",
    ".yml",
}

DESIGN_KEYWORDS = (
    "a11y",
    "accessibility",
    "agent",
    "app",
    "badge",
    "button",
    "card",
    "component",
    "design",
    "dialog",
    "drawer",
    "footer",
    "form",
    "global",
    "header",
    "input",
    "layout",
    "modal",
    "nav",
    "page",
    "playwright",
    "product",
    "readme",
    "select",
    "sheet",
    "sidebar",
    "style",
    "table",
    "tabs",
    "tailwind",
    "theme",
    "typography",
    "ui",
)

MAX_FILES = 180
MAX_BYTES = 128_000


def inspect_repository(root: str | Path) -> RepositorySnapshot:
    root_path = Path(root).resolve()
    candidate_files = _select_candidate_files(root_path)
    contents = {path: _read_text(path) for path in candidate_files}

    package_info = _load_package_info(root_path / "package.json")
    dependencies = set(package_info.get("dependencies", {})) | set(
        package_info.get("devDependencies", {})
    )

    authorities = _collect_authorities(root_path, candidate_files)
    frontend = _detect_frontend(dependencies, candidate_files)
    styling = _detect_styling(dependencies, candidate_files, contents)
    component_system = _detect_component_system(root_path, dependencies, authorities)
    design_tokens = _detect_design_tokens(contents, candidate_files)
    typography = _detect_typography(contents, candidate_files)
    design_documentation = _detect_design_docs(authorities)
    agent_governance = _presence_from_paths(
        authorities.get("agent_governance", []), "Repository instructions found."
    )
    playwright = _detect_playwright(dependencies, candidate_files)
    accessibility_tooling = _detect_accessibility(dependencies, contents, candidate_files)
    existing_design_skills = _detect_existing_design_skills(root_path)
    notes = _build_notes(authorities, component_system, existing_design_skills)

    maturity = _classify_maturity(
        frontend=frontend,
        styling=styling,
        component_system=component_system,
        design_tokens=design_tokens,
        design_documentation=design_documentation,
        agent_governance=agent_governance,
        playwright=playwright,
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
        accessibility_tooling=accessibility_tooling,
        existing_design_skills=existing_design_skills,
        authorities=authorities,
        notes=notes,
    )


def _select_candidate_files(root: Path) -> list[Path]:
    selected: list[Path] = []
    seen: set[Path] = set()

    for relative_name in EXPLICIT_FILES:
        path = root / relative_name
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
            if len(relative.parts) > 3:
                dirnames[:] = []
                continue
            dirnames[:] = [name for name in dirnames if name not in IGNORED_DIR_NAMES]
            for filename in filenames:
                path = current / filename
                if path in seen or not _looks_design_relevant(path, base):
                    continue
                selected.append(path)
                seen.add(path)
                if len(selected) >= MAX_FILES:
                    return sorted(selected)
    return sorted(selected)


def _looks_design_relevant(path: Path, base: Path) -> bool:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return False
    try:
        relative = str(path.relative_to(base)).lower()
    except ValueError:
        relative = path.name.lower()
    if base.name in {"docs", "design", "architecture", "product"}:
        return True
    return any(keyword in relative for keyword in DESIGN_KEYWORDS)


def _read_text(path: Path) -> str:
    if path.stat().st_size > MAX_BYTES:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _load_package_info(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _collect_authorities(root: Path, candidate_files: list[Path]) -> dict[str, list[str]]:
    authorities: dict[str, list[str]] = defaultdict(list)
    for path in candidate_files:
        relative = str(path.relative_to(root))
        lowered = relative.lower()
        if path.name in {"AGENTS.md", "CLAUDE.md"}:
            authorities["agent_governance"].append(relative)
        if "design" in lowered or "ui" in lowered or "product" in lowered:
            if path.suffix.lower() in {".md", ".mdx"}:
                authorities["design_docs"].append(relative)
        if "playwright" in lowered or "/e2e/" in lowered or lowered.startswith("tests/e2e"):
            authorities["playwright"].append(relative)
        if lowered.startswith("components/ui/"):
            authorities["component_primitives"].append(relative)
        if path.suffix.lower() == ".css":
            authorities["style_files"].append(relative)
    for folder_name in ("components", "components2", "ui", "shared-ui", "design-system"):
        folder = root / folder_name
        if folder.exists():
            authorities["component_directories"].append(folder_name)
    return {key: sorted(values) for key, values in authorities.items()}


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
    if any(path.name.endswith(".module.css") for path in candidate_files):
        return "CSS Modules"
    if any(path.suffix == ".css" for path in candidate_files):
        return "CSS"
    return "Unknown"


def _detect_component_system(
    root: Path, dependencies: set[str], authorities: dict[str, list[str]]
) -> str:
    if (root / "components/ui").exists() and any(dep.startswith("@radix-ui/") for dep in dependencies):
        return "shadcn + local primitives"
    component_dirs = authorities.get("component_directories", [])
    if len(component_dirs) >= 3:
        return "Mixed local primitives"
    if (root / "components").exists():
        return "Local components"
    return "Unknown"


def _detect_design_tokens(contents: dict[Path, str], candidate_files: list[Path]) -> CapabilitySignal:
    evidence: list[str] = []
    for path, text in contents.items():
        if "tailwind.config" in path.name and "extend" in text:
            evidence.append(str(path.name))
        if path.suffix == ".css" and "--" in text and ":" in text:
            evidence.append(str(path.name))
    return _signal_from_evidence(evidence, "Detected theme extensions or CSS custom properties.")


def _detect_typography(contents: dict[Path, str], candidate_files: list[Path]) -> CapabilitySignal:
    evidence: list[str] = []
    for path, text in contents.items():
        if "fontFamily" in text or "next/font" in text or "@font-face" in text:
            evidence.append(str(path.name))
    return _signal_from_evidence(evidence, "Detected explicit typography configuration.")


def _detect_design_docs(authorities: dict[str, list[str]]) -> CapabilitySignal:
    design_docs = authorities.get("design_docs", [])
    if len(design_docs) >= 2:
        return CapabilitySignal(
            status=Presence.PARTIAL,
            evidence=design_docs,
            note="Multiple design authorities detected; reconcile before adding more.",
        )
    return _presence_from_paths(design_docs, "Repository already records design intent.")


def _detect_playwright(dependencies: set[str], candidate_files: list[Path]) -> CapabilitySignal:
    evidence = []
    if "@playwright/test" in dependencies:
        evidence.append("package.json")
    evidence.extend(
        str(path.name)
        for path in candidate_files
        if "playwright" in path.name or "e2e" in str(path).lower()
    )
    return _signal_from_evidence(sorted(set(evidence)), "Playwright or e2e evidence found.")


def _detect_accessibility(
    dependencies: set[str], contents: dict[Path, str], candidate_files: list[Path]
) -> CapabilitySignal:
    evidence: list[str] = []
    for dep in ("eslint-plugin-jsx-a11y", "axe-core", "@axe-core/playwright"):
        if dep in dependencies:
            evidence.append("package.json")
            break
    for path, text in contents.items():
        if "aria-" in text or "accessibility" in text.lower():
            evidence.append(str(path.name))
    if evidence:
        status = Presence.PRESENT if "package.json" in evidence else Presence.PARTIAL
        return CapabilitySignal(status=status, evidence=sorted(set(evidence)))
    return CapabilitySignal(status=Presence.NONE, evidence=[])


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
            }:
                evidence.append(f"skills/{child.name}")
    return _signal_from_evidence(evidence, "Design Intelligence skills are already present.")


def _signal_from_evidence(evidence: list[str], note: str) -> CapabilitySignal:
    if not evidence:
        return CapabilitySignal(status=Presence.NONE, evidence=[])
    return CapabilitySignal(status=Presence.PRESENT, evidence=sorted(set(evidence)), note=note)


def _presence_from_paths(paths: list[str], note: str) -> CapabilitySignal:
    if not paths:
        return CapabilitySignal(status=Presence.NONE, evidence=[])
    return CapabilitySignal(status=Presence.PRESENT, evidence=paths, note=note)


def _build_notes(
    authorities: dict[str, list[str]],
    component_system: str,
    existing_design_skills: CapabilitySignal,
) -> list[str]:
    notes: list[str] = []
    if len(authorities.get("design_docs", [])) >= 2:
        notes.append("Possible dual design authority detected.")
    if component_system == "Mixed local primitives":
        notes.append("Multiple component directories suggest convergence risk.")
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
) -> RepositoryMaturity:
    score = 0
    if frontend != "Unknown":
        score += 1
    if styling != "Unknown":
        score += 1
    if component_system != "Unknown":
        score += 1
    if design_tokens.status == Presence.PRESENT:
        score += 1
    if design_documentation.status != Presence.NONE:
        score += 1
    if agent_governance.status == Presence.PRESENT:
        score += 1
    if playwright.status != Presence.NONE:
        score += 1
    if score >= 6:
        return RepositoryMaturity.ESTABLISHED
    if score >= 3:
        return RepositoryMaturity.PARTIAL
    return RepositoryMaturity.GREENFIELD


def render_snapshot_text(snapshot: RepositorySnapshot) -> str:
    sections = [
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
        f"Accessibility tooling: {snapshot.accessibility_tooling.status.value}",
        "",
        "Files considered:",
    ]
    sections.extend(f"- {path}" for path in snapshot.files_considered)
    if snapshot.notes:
        sections.extend(["", "Notes:"])
        sections.extend(f"- {note}" for note in snapshot.notes)
    return "\n".join(sections)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect a repository for repo-fit signals.")
    parser.add_argument("--root", default=".", help="Repository root to inspect.")
    parser.add_argument(
        "--format",
        choices=("json", "text"),
        default="text",
        help="Output format.",
    )
    args = parser.parse_args(argv)

    snapshot = inspect_repository(args.root)
    if args.format == "json":
        print(json.dumps(snapshot.to_dict(), indent=2))
    else:
        print(render_snapshot_text(snapshot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
