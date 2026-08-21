from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path

from .models import LintFinding, LintReport, LintStatus, Severity
from .repository import select_candidate_files

COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}")
ARBITRARY_RE = re.compile(r"(?:p|px|py|pt|pb|pl|pr|m|mx|my|mt|mb|gap|rounded|min-w|max-w|w|h)-\[[^\]]+\]")
WIDTH_RE = re.compile(r"(?:min-w|w)-\[(\d+)px\]")
IMG_RE = re.compile(r"<img\b(?![^>]*\balt=)[^>]*>")
BUTTON_RE = re.compile(r"<button\b([^>]*)>(.*?)</button>", re.DOTALL)
ICON_ONLY_RE = re.compile(r"^(?:\s|<[^>]+>)*$")
IGNORE_RE = re.compile(r"design-intelligence:\s*ignore\s+([a-z0-9\-_, ]+)")
COMPONENT_DIR_RE = re.compile(r"(?:^|/)(?:components|components2|ui|shared-ui|design-system|src/components)/")
PRIMITIVE_NAMES = {"Button", "Card", "Dialog", "Input", "Modal", "Table", "Tabs", "Badge"}


def run_lint(root: str | Path) -> LintReport:
    root_path = Path(root).resolve()
    files = select_candidate_files(root_path)
    findings: list[LintFinding] = []
    intentional_exceptions: list[str] = []
    component_candidates: defaultdict[str, list[str]] = defaultdict(list)

    for path in files:
        relative = str(path.relative_to(root_path))
        text = path.read_text(encoding="utf-8", errors="ignore")
        ignored_rules = _ignored_rules(text)
        intentional_exceptions.extend(f"{relative}:{rule}" for rule in sorted(ignored_rules))
        lines = text.splitlines()
        for line_number, line in enumerate(lines, start=1):
            stripped = line.strip()
            if (
                "token-hardcoded-color" not in ignored_rules
                and COLOR_RE.search(line)
                and not _looks_like_token_definition(stripped)
                and path.suffix.lower() in {".css", ".tsx", ".jsx", ".ts", ".js"}
            ):
                findings.append(
                    LintFinding(
                        rule_id="token-hardcoded-color",
                        category="token",
                        severity=Severity.P2,
                        file=relative,
                        line=line_number,
                        message="Hard-coded color found outside an obvious token definition.",
                        evidence=stripped,
                        repairable=False,
                    )
                )
            arbitrary = ARBITRARY_RE.search(line)
            if arbitrary and "token-arbitrary-value" not in ignored_rules:
                findings.append(
                    LintFinding(
                        rule_id="token-arbitrary-value",
                        category="token",
                        severity=Severity.P2,
                        file=relative,
                        line=line_number,
                        message="Arbitrary utility value may indicate token or spacing drift.",
                        evidence=arbitrary.group(0),
                        repairable=False,
                    )
                )
            width = WIDTH_RE.search(line)
            if width and "layout-unsafe-width" not in ignored_rules and int(width.group(1)) > 480:
                findings.append(
                    LintFinding(
                        rule_id="layout-unsafe-width",
                        category="layout",
                        severity=Severity.P1,
                        file=relative,
                        line=line_number,
                        message="Large fixed width risks overflow or off-screen content on smaller viewports.",
                        evidence=width.group(0),
                        repairable=True,
                    )
                )
            if "left-[" in line and "layout-offscreen-position" not in ignored_rules:
                findings.append(
                    LintFinding(
                        rule_id="layout-offscreen-position",
                        category="layout",
                        severity=Severity.P1,
                        file=relative,
                        line=line_number,
                        message="Potential off-screen positioning detected.",
                        evidence=stripped,
                        repairable=True,
                    )
                )
        if path.suffix.lower() in {".tsx", ".jsx", ".html"}:
            findings.extend(_img_findings(relative, text, ignored_rules))
            findings.extend(_button_findings(relative, text, ignored_rules))
        if COMPONENT_DIR_RE.search(relative) and path.stem in PRIMITIVE_NAMES:
            component_candidates[path.stem].append(relative)

    findings.extend(_duplicate_primitive_findings(component_candidates))
    counts = Counter(finding.category for finding in findings)
    status = _status(findings)
    notes = _notes(findings, component_candidates)
    return LintReport(
        root=str(root_path),
        findings=findings,
        intentional_exceptions=sorted(set(intentional_exceptions)),
        status=status,
        counts=dict(sorted(counts.items())),
        notes=notes,
    )


def _ignored_rules(text: str) -> set[str]:
    ignored: set[str] = set()
    for match in IGNORE_RE.finditer(text):
        for item in match.group(1).split(","):
            ignored.add(item.strip())
    return ignored


def _looks_like_token_definition(line: str) -> bool:
    return line.startswith("--") or ":root" in line or "var(" in line


def _img_findings(relative: str, text: str, ignored_rules: set[str]) -> list[LintFinding]:
    findings: list[LintFinding] = []
    if "a11y-image-alt" in ignored_rules:
        return findings
    for match in IMG_RE.finditer(text):
        line = text[: match.start()].count("\n") + 1
        findings.append(
            LintFinding(
                rule_id="a11y-image-alt",
                category="accessibility",
                severity=Severity.P1,
                file=relative,
                line=line,
                message="Image element is missing an alt attribute.",
                evidence=match.group(0),
                repairable=True,
            )
        )
    return findings


def _button_findings(relative: str, text: str, ignored_rules: set[str]) -> list[LintFinding]:
    findings: list[LintFinding] = []
    if "a11y-icon-button-name" in ignored_rules:
        return findings
    for match in BUTTON_RE.finditer(text):
        attrs, inner = match.groups()
        if "aria-label" in attrs or "aria-labelledby" in attrs or "title=" in attrs:
            continue
        if ICON_ONLY_RE.match(inner):
            line = text[: match.start()].count("\n") + 1
            findings.append(
                LintFinding(
                    rule_id="a11y-icon-button-name",
                    category="accessibility",
                    severity=Severity.P1,
                    file=relative,
                    line=line,
                    message="Icon-only button is missing an accessible name.",
                    evidence=match.group(0).strip(),
                    repairable=True,
                )
            )
    return findings


def _duplicate_primitive_findings(component_candidates: dict[str, list[str]]) -> list[LintFinding]:
    findings: list[LintFinding] = []
    for primitive, paths in component_candidates.items():
        if len(paths) < 2:
            continue
        findings.append(
            LintFinding(
                rule_id="component-duplicate-primitive",
                category="component",
                severity=Severity.P1,
                file=paths[0],
                line=1,
                message=f"Multiple {primitive} primitives found across competing UI directories.",
                evidence=", ".join(paths),
                repairable=False,
            )
        )
    return findings


def _status(findings: list[LintFinding]) -> LintStatus:
    severities = {finding.severity for finding in findings}
    if Severity.P0 in severities or Severity.P1 in severities:
        return LintStatus.FAIL
    if findings:
        return LintStatus.WARN
    return LintStatus.PASS


def _notes(findings: list[LintFinding], component_candidates: dict[str, list[str]]) -> list[str]:
    notes = []
    if any(finding.category == "token" for finding in findings):
        notes.append("Token drift findings are deterministic hints; confirm intentional exceptions before changing visuals.")
    if any(len(paths) >= 2 for paths in component_candidates.values()):
        notes.append("Duplicate primitives should converge through compatibility seams rather than broad rewrites.")
    if any(finding.category == "accessibility" for finding in findings):
        notes.append("Accessibility findings marked repairable are candidates for a bounded repair plan, not silent auto-mutation.")
    return notes


def render_lint_text(report: LintReport) -> str:
    lines = [
        "DESIGN LINTER",
        "",
        f"Root: {report.root}",
        f"Status: {report.status.value}",
        "Counts:",
    ]
    if report.counts:
        lines.extend(f"- {category}: {count}" for category, count in report.counts.items())
    else:
        lines.append("- none")
    lines.extend(["", "Findings:"])
    if report.findings:
        for finding in report.findings:
            lines.append(
                f"- {finding.severity.value} {finding.rule_id} {finding.file}:{finding.line} {finding.message}"
            )
    else:
        lines.append("- none")
    if report.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {item}" for item in report.notes)
    return "\n".join(lines)
